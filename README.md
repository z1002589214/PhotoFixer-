# 📷 PhotoFixer - 照片/视频元数据批量修复工具

[![Version](https://img.shields.io/badge/version-1.0-blue.svg)](https://github.com/yourname/PhotoFixer)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-brightgreen.svg)](https://github.com/yourname/PhotoFixer)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/yourname/PhotoFixer)

PhotoFixer 是一款用于**批量修复照片和视频元数据**的 Windows 工具。它能从文件名中提取日期时间，写入文件内部的 EXIF/XMP/QuickTime 元数据，让苹果相册、Lightroom 等软件能正确识别文件的拍摄时间。

---

## ✨ 功能特性

- 🚀 **多线程并发处理** - 速度提升 3~5 倍
- 📁 **支持多种格式** - JPEG / PNG / GIF / HEIC / MP4 / MOV / M4V / 3GP
- 🔍 **自动识别日期格式** - 支持多种文件名命名规则
- 🔄 **自动修正后缀错误** - 检测并修正伪装文件（如 `.jpg` 伪装成 `.png`）
- ⭐ **自动标记星级** - 有日期 5 星，PNG 4 星，无日期 3 星
- 📅 **自定义时间范围** - 避免将纯数字编号误认为日期
- 💾 **创建日期备选** - 文件名无日期时，可使用文件创建日期
- 📊 **实时进度显示** - 进度条 + 预估剩余时间
- 🖱️ **交互式操作** - 支持拖拽文件夹，无需记忆命令行
- 📦 **单文件打包** - 无需安装 Python，直接双击运行

---

## 📂 支持的文件格式

| 格式 | 扩展名 | 写入的元数据标签 | 星级（有日期时） |
|------|--------|----------------|----------------|
| JPEG | `.jpg` `.jpeg` | `DateTimeOriginal`、`CreateDate`、`ModifyDate` | ⭐⭐⭐⭐⭐ 5星 |
| PNG | `.png` | `XMP:CreateDate`、`PNG:CreationTime` | ⭐⭐⭐⭐ 4星 |
| GIF | `.gif` | `XMP:CreateDate`、`XMP:ModifyDate` | ⭐⭐⭐⭐⭐ 5星 |
| HEIC | `.heic` | `DateTimeOriginal`、`CreateDate`、`ModifyDate` | ⭐⭐⭐⭐⭐ 5星 |
| 视频 | `.mp4` `.mov` `.m4v` `.3gp` | `CreateDate`、`MediaCreateDate`、`TrackCreateDate` | ⭐⭐⭐⭐⭐ 5星 |

---

## 📅 支持的文件名格式

| 文件名示例 | 提取结果 |
|-----------|---------|
| `wx_camera_1549879050182.jpg` | 2019-02-11 17:57:30 |
| `Screenshot_20190211-125802.jpg` | 2019-02-11 12:58:02 |
| `2018-10-02 124301.png` | 2018-10-02 12:43:01 |
| `IMG_20180529_162344.jpg` | 2018-05-29 16:23:44 |
| `Screenshot_20180612-120612.png` | 2018-06-12 12:06:12 |
| `1497458181082.jpeg` | 2017-06-14 16:36:21 |
| `video_20190519_064521.mp4` | 2019-05-19 06:45:21 |

---
