import os
import re
import subprocess
import sys
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

# ---------- 配置 ----------
MAX_WORKERS = 8  # 同时处理的最大线程数

# 所有支持的文件扩展名（统一小写，不带点）
SUPPORTED_EXTS = {'jpg', 'jpeg', 'png', 'gif', 'heic', 'mp4', 'mov', 'm4v', '3gp'}

# ---------- 1. 从文件名提取日期时间 ----------
def extract_datetime(filename, min_year, max_year):
    name = os.path.splitext(filename)[0]
    
    patterns = [
        r'wx_camera_(\d{13})',
        r'Screenshot_(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})',
        r'(\d{4})-(\d{2})-(\d{2})[ _](\d{2})(\d{2})(\d{2})',
        r'(\d{4})(\d{2})(\d{2})[_-](\d{2})(\d{2})(\d{2})',
        r'(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{2})',
        r'(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})',
        r'\b(\d{10,13})\b',
        r'video_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})',
    ]
    
    for pat in patterns:
        m = re.search(pat, name)
        if m:
            nums = list(map(int, m.groups()))
            if len(nums) == 1:
                ts = nums[0]
                if ts > 1e12:
                    ts /= 1000
                try:
                    dt = datetime.fromtimestamp(ts)
                    if min_year <= dt.year <= max_year:
                        return dt
                    else:
                        continue
                except (OSError, ValueError):
                    continue
            elif len(nums) == 6:
                try:
                    dt = datetime(nums[0], nums[1], nums[2], nums[3], nums[4], nums[5])
                    if min_year <= dt.year <= max_year:
                        return dt
                    else:
                        continue
                except ValueError:
                    continue
    return None

# ---------- 2. 获取文件的创建日期 ----------
def get_file_creation_date(file_path):
    try:
        result = subprocess.run(
            ['exiftool', '-FileCreateDate', '-s3', file_path],
            capture_output=True, text=True, timeout=5
        )
        date_str = result.stdout.strip()
        if date_str:
            dt = datetime.strptime(date_str, '%Y:%m:%d %H:%M:%S')
            return dt
    except:
        pass
    return None

# ---------- 3. 检测文件真实格式（文件头魔数检测） ----------
def get_real_type(file_path):
    try:
        with open(file_path, 'rb') as f:
            header = f.read(12)
        
        # JPEG
        if header[:3] == b'\xff\xd8\xff':
            return 'jpeg'
        # PNG
        if header[:4] == b'\x89PNG':
            return 'png'
        # GIF
        if header[:6] in (b'GIF89a', b'GIF87a'):
            return 'gif'
        # BMP
        if header[:2] == b'BM':
            return 'bmp'
        # WebP
        if header[:4] == b'RIFF' and header[8:12] == b'WEBP':
            return 'webp'
        # MP4 / MOV / M4V / 3GP / HEIC (ftyp container)
        if header[4:8] == b'ftyp':
            major_brand = header[8:12]
            if major_brand in (b'isom', b'iso2', b'mp41', b'mp42', b'msnv'):
                return 'mp4'
            if major_brand in (b'qt  ', b'qt '):
                return 'mov'
            if major_brand == b'M4V ':
                return 'm4v'
            if major_brand in (b'3gp', b'3g2'):
                return '3gp'
            if major_brand in (b'heic', b'heix', b'mif1', b'msf1'):
                return 'heic'
            return 'mp4'
        # PDF
        if header[:4] == b'%PDF':
            return 'pdf'
        # ZIP
        if header[:2] == b'PK':
            return 'zip'
        return None
    except Exception:
        return None

# ---------- 4. 修正文件后缀 ----------
def fix_extension(file_path, correct_ext):
    dirname = os.path.dirname(file_path)
    basename = os.path.basename(file_path)
    name_without_ext = os.path.splitext(basename)[0]
    new_path = os.path.join(dirname, name_without_ext + correct_ext)
    
    try:
        os.rename(file_path, new_path)
        return new_path
    except Exception as e:
        print(f'    ❌ 重命名失败: {e}')
        return None

# ---------- 5. 写入元数据（图片） ----------
def set_image_metadata(file_path, dt_obj, file_ext):
    cmd = ['exiftool', '-overwrite_original']
    ext_lower = file_ext.lower()
    
    if dt_obj is None:
        cmd.extend(['-Rating=3', '-XMP:Rating=3'])
    else:
        time_str = dt_obj.strftime('%Y:%m:%d %H:%M:%S')
        
        if ext_lower in ('.jpg', '.jpeg'):
            cmd.extend([
                f'-DateTimeOriginal={time_str}',
                f'-CreateDate={time_str}',
                f'-ModifyDate={time_str}',
                '-Rating=5',
                '-XMP:Rating=5'
            ])
        elif ext_lower == '.png':
            cmd.extend([
                f'-XMP:CreateDate={time_str}',
                f'-XMP:ModifyDate={time_str}',
                f'-PNG:CreationTime={time_str}',
                f'-PNG:ModifyTime={time_str}',
                '-Rating=4',
                '-XMP:Rating=4'
            ])
        elif ext_lower == '.heic':
            cmd.extend([
                f'-DateTimeOriginal={time_str}',
                f'-CreateDate={time_str}',
                f'-ModifyDate={time_str}',
                '-Rating=5',
                '-XMP:Rating=5'
            ])
        elif ext_lower == '.gif':
            cmd.extend([
                f'-XMP:CreateDate={time_str}',
                f'-XMP:ModifyDate={time_str}',
                '-Rating=5',
                '-XMP:Rating=5'
            ])
        else:
            return False
    
    cmd.append(file_path)
    
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=10)
        return True
    except subprocess.CalledProcessError as e:
        return False
    except subprocess.TimeoutExpired:
        return False

# ---------- 6. 写入元数据（视频） ----------
def set_video_metadata(file_path, dt_obj):
    cmd = ['exiftool', '-overwrite_original']
    
    if dt_obj is None:
        cmd.extend(['-Rating=3', '-XMP:Rating=3'])
    else:
        time_str = dt_obj.strftime('%Y:%m:%d %H:%M:%S')
        cmd.extend([
            f'-CreateDate={time_str}',
            f'-ModifyDate={time_str}',
            f'-MediaCreateDate={time_str}',
            f'-MediaModifyDate={time_str}',
            f'-TrackCreateDate={time_str}',
            f'-TrackModifyDate={time_str}',
            '-Rating=5',
            '-XMP:Rating=5'
        ])
    
    cmd.append(file_path)
    
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=10)
        return True
    except subprocess.CalledProcessError as e:
        return False
    except subprocess.TimeoutExpired:
        return False

# ---------- 7. 处理单个文件（用于多线程） ----------
def process_single_file(file_info):
    file_path, fn, dt_obj, file_ext = file_info
    ext_lower = file_ext.lower()
    is_video = ext_lower in ('.mp4', '.mov', '.m4v', '.3gp')
    
    if is_video:
        success = set_video_metadata(file_path, dt_obj)
    else:
        success = set_image_metadata(file_path, dt_obj, file_ext)
    
    return {
        'file_path': file_path,
        'filename': fn,
        'success': success,
        'has_time': dt_obj is not None
    }

# ---------- 8. 询问用户 ----------
def ask_user(question):
    while True:
        answer = input(f'{question} (y/n): ').strip().lower()
        if answer in ('y', 'n'):
            return answer == 'y'
        print('   请输入 y 或 n')

# ---------- 9. 获取时间范围 ----------
def get_year_range():
    print('\n' + '=' * 70)
    print('📅 请设置时间范围（用于判断文件名中的数字是否为有效日期）')
    print('   提示：只会提取年份在指定范围内的日期，超出范围的将被忽略。')
    print()
    
    while True:
        try:
            min_year = input('请输入年份下限（例如 2015）: ').strip()
            if not min_year:
                min_year = 2015
                print(f'   使用默认值: {min_year}')
            else:
                min_year = int(min_year)
            
            max_year = input('请输入年份上限（例如 2026）: ').strip()
            if not max_year:
                max_year = 2026
                print(f'   使用默认值: {max_year}')
            else:
                max_year = int(max_year)
            
            if min_year > max_year:
                print('❌ 年份下限不能大于上限，请重新输入。')
                continue
            
            print(f'✅ 时间范围已设置: {min_year} ~ {max_year}')
            return min_year, max_year
        
        except ValueError:
            print('❌ 请输入有效的数字！')

# ---------- 10. 询问是否使用创建日期 ----------
def ask_use_creation_date():
    print('\n' + '-' * 70)
    print('📂 当文件名中提取不到日期时，可以选择使用文件的')
    print('   "创建日期"（文件写入磁盘的时间）作为备选。')
    print('   注意：这通常不是照片的实际拍摄时间，但可以避免时间线混乱。')
    return ask_user('是否使用文件创建日期作为备选？')

# ---------- 11. 扫描文件 ----------
def scan_files(folder, min_year, max_year, use_creation_date):
    print('\n' + '-' * 70)
    print('📷 正在扫描文件，检测真实格式...')
    
    ext_whitelist = tuple('.' + ext for ext in SUPPORTED_EXTS)
    
    print('⏳ 正在遍历文件夹...')
    file_paths = []
    for root, dirs, files in os.walk(folder):
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext in ext_whitelist:
                file_paths.append(os.path.join(root, fname))
    
    if not file_paths:
        print('⚠️ 该文件夹内未找到任何支持的文件。')
        return [], []
    
    print(f'✅ 找到 {len(file_paths)} 个文件，正在分析...\n')
    
    all_files = []
    disguised_list = []
    
    for full_path in tqdm(file_paths, desc='🔍 分析文件', unit='个'):
        fname = os.path.basename(full_path)
        ext = os.path.splitext(fname)[1].lower()
        real_type = get_real_type(full_path)
        
        is_disguised = False
        if real_type and real_type in SUPPORTED_EXTS:
            current_ext = ext[1:]
            if current_ext != real_type:
                is_disguised = True
                disguised_list.append((full_path, ext, real_type))
        
        dt = extract_datetime(fname, min_year, max_year)
        if dt is None and use_creation_date:
            dt = get_file_creation_date(full_path)
        
        all_files.append((full_path, fname, dt, ext, real_type, is_disguised))
    
    print(f'\n📊 扫描完成！共 {len(all_files)} 个文件。')
    print(f'   ⚠️ 发现 {len(disguised_list)} 个后缀伪装文件。')
    
    return all_files, disguised_list

# ---------- 12. 多线程写入 ----------
def multithread_write(final_files):
    total = len(final_files)
    if total == 0:
        return 0
    
    print('\n' + '-' * 70)
    print(f'🚀 开始正式写入元数据（多线程模式，{MAX_WORKERS} 个线程并发）...\n')
    
    success_count = 0
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(process_single_file, file_info): file_info
            for file_info in final_files
        }
        
        with tqdm(total=total, desc='⏳ 写入进度', unit='个') as pbar:
            for future in as_completed(futures):
                result = future.result()
                if result['success']:
                    success_count += 1
                else:
                    tqdm.write(f'   ❌ 处理失败: {result["filename"]}')
                
                pbar.update(1)
                
                if pbar.n % 10 == 0 or pbar.n == total:
                    elapsed = time.time() - start_time
                    processed = pbar.n
                    if processed > 0:
                        avg_time = elapsed / processed
                        remaining = total - processed
                        eta_seconds = remaining * avg_time
                        
                        if eta_seconds < 60:
                            eta_str = f'{eta_seconds:.0f} 秒'
                        elif eta_seconds < 3600:
                            eta_str = f'{eta_seconds/60:.1f} 分钟'
                        else:
                            eta_str = f'{eta_seconds/3600:.1f} 小时'
                        
                        tqdm.write(f'   📊 已处理 {processed}/{total} | 预计剩余: {eta_str} | 速度: {processed/elapsed:.1f} 个/秒')
    
    return success_count

# ---------- 13. 获取文件夹路径（支持命令行参数和交互输入） ----------
def get_folder_path():
    # 如果命令行提供了路径参数，直接使用
    if len(sys.argv) >= 2:
        folder = sys.argv[1]
        if os.path.isdir(folder):
            return folder
        else:
            print(f'❌ 错误：命令行指定的文件夹 "{folder}" 不存在。')
            # 继续询问用户输入
    
    # 交互模式：询问用户输入路径
    print('\n' + '=' * 70)
    print('📁 欢迎使用照片/视频元数据批量修复工具')
    print('=' * 70)
    print()
    print('💡 使用说明：')
    print('   1. 请将要处理的照片和视频放在一个文件夹中')
    print('   2. 输入该文件夹的完整路径')
    print('   3. 也可以直接将文件夹拖拽到本窗口后按回车')
    print()
    
    while True:
        folder = input('📂 请输入文件夹路径: ').strip()
        # 移除路径两端的引号（如果有）
        folder = folder.strip('"').strip("'")
        if not folder:
            print('❌ 路径不能为空，请重新输入。')
            continue
        if os.path.isdir(folder):
            return folder
        else:
            print(f'❌ 文件夹 "{folder}" 不存在，请检查路径是否正确。')
            print('   💡 提示：可以将文件夹直接拖拽到本窗口，然后按回车。')
            print()

# ---------- 14. 主程序 ----------
def main():
    # ========== 第一步：获取文件夹路径 ==========
    folder = get_folder_path()
    print(f'\n✅ 目标文件夹: {folder}')

    # ========== 第二步：获取用户配置 ==========
    min_year, max_year = get_year_range()
    use_creation_date = ask_use_creation_date()

    # ========== 第三步：环境诊断 ==========
    print('\n' + '=' * 70)
    print('🔍 正在进行环境诊断...')
    try:
        result = subprocess.run(['exiftool', '-ver'], capture_output=True, text=True, check=True)
        print(f'✅ ExifTool 版本: {result.stdout.strip()} (环境正常)')
    except:
        print('❌ 错误：找不到 exiftool 命令！')
        print('   请下载 exiftool.exe 并放到 C:\\Windows 目录，或放到本脚本同目录下。')
        input('\n按 Enter 键退出...')
        return

    # ========== 第四步：扫描文件 ==========
    all_files, disguised_list = scan_files(folder, min_year, max_year, use_creation_date)
    if not all_files:
        input('\n按 Enter 键退出...')
        return

    # ========== 第五步：显示伪装文件列表并询问修正 ==========
    if disguised_list:
        print('\n' + '-' * 70)
        print('📋 发现以下后缀伪装文件（文件名 → 真实格式）：')
        for full_path, current_ext, real_type in disguised_list:
            fname = os.path.basename(full_path)
            print(f'   - {fname}  (当前后缀 {current_ext}，真实格式 {real_type})')
        
        print(f'\n⚠️ 共 {len(disguised_list)} 个文件后缀与实际格式不符。')
        print('   修正操作：将自动重命名为正确的后缀（如 .jpg → .png）。')
        if ask_user('是否修正所有伪装文件？'):
            print('\n🔄 正在重命名伪装文件...')
            for full_path, current_ext, real_type in tqdm(disguised_list, desc='   重命名', unit='个'):
                correct_ext = '.' + real_type
                new_path = fix_extension(full_path, correct_ext)
                if new_path:
                    fname = os.path.basename(new_path)
                    for i, (old_path, old_fname, dt, old_ext, rt, dis) in enumerate(all_files):
                        if old_path == full_path:
                            all_files[i] = (new_path, fname, dt, correct_ext, real_type, False)
                            break
                else:
                    print(f'   ❌ 重命名失败: {os.path.basename(full_path)}')
        else:
            print('⏭️ 跳过修正伪装文件。')

    # ========== 第六步：生成预览 ==========
    print('\n' + '-' * 70)
    print('📋 正在生成元数据写入预览...\n')
    
    final_files = []
    for fp, fn, dt, ext, rt, dis in tqdm(all_files, desc='📋 生成预览', unit='个'):
        if not os.path.exists(fp):
            continue
        final_files.append((fp, fn, dt, ext))
    
    print('\n' + '-' * 70)
    print('📋 预览清单（前10个文件，其余类似）：\n')
    
    display_count = min(10, len(final_files))
    for i in range(display_count):
        fp, fn, dt, ext = final_files[i]
        real = get_real_type(fp) or ext[1:]
        is_video = ext in ('.mp4', '.mov', '.m4v', '.3gp')
        
        if dt is None:
            status = '⏭️ 无时间 -> 仅设3星'
        elif is_video:
            status = '🎬 视频 -> 写入QuickTime时间 + 5星'
        elif ext in ('.jpg', '.jpeg'):
            status = '📸 JPEG -> 写入EXIF时间 + 5星'
        elif ext == '.png':
            status = '🖼️ PNG  -> 写入XMP时间 + 4星'
        elif ext == '.heic':
            status = '📱 HEIC -> 写入EXIF时间 + 5星'
        elif ext == '.gif':
            status = '🎞️ GIF  -> 写入XMP时间 + 5星'
        else:
            status = '❓ 未知格式'
        
        time_str = dt.strftime('%Y-%m-%d %H:%M:%S') if dt else '未提取到'
        date_source = '（从文件名提取）' if dt else '（使用创建日期）' if use_creation_date else ''
        
        print(f'  📄 {fn}')
        print(f'     -> 提取时间: {time_str} {date_source}')
        print(f'     -> 真实格式: {real}')
        print(f'     -> 操作计划: {status}')
        print()
    
    if len(final_files) > 10:
        print(f'  ... 还有 {len(final_files) - 10} 个文件未显示（处理时仍会全部操作）\n')
    
    print('-' * 70)
    print(f'✅ 预览生成完成！共 {len(final_files)} 个文件待处理。')
    print('⏳ 等待您的确认...')
    print('-' * 70)

    # ========== 第七步：最终确认 ==========
    print('-' * 70)
    print(f'📊 共 {len(final_files)} 个文件待处理。')
    print(f'📅 时间范围: {min_year} ~ {max_year}')
    print('⚠️ 确认无误后，输入 y 开始正式写入元数据（操作不可逆，请确认已备份）。')
    print('   输入 n 取消操作，不修改任何文件。')
    
    if not ask_user('是否继续写入元数据？'):
        print('🛑 已取消操作，未修改任何文件。')
        input('\n按 Enter 键退出...')
        return
    
    # ========== 第八步：多线程写入 ==========
    success_count = multithread_write(final_files)
    
    # ========== 完成总结 ==========
    print('\n' + '-' * 70)
    print(f'🎉 全部完成！成功处理 {success_count} / {len(final_files)} 个文件。')
    print('💡 提示：请打开苹果相册或看图软件，查看照片/视频的拍摄时间和星级是否正确。')
    input('\n按 Enter 键退出...')

if __name__ == '__main__':
    main()