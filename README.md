# VideoDL — 视频下载器 GUI

基于 [yt-dlp](https://github.com/yt-dlp/yt-dlp) + tkinter 的桌面视频下载工具，支持多平台、代理、Cookie、自动命名和进度反馈。

## 功能

- 🖥️ **图形界面** — 基于 Python tkinter，开箱即用
- 🌐 **多平台支持** — YouTube、Bilibili、抖音 等（由 yt-dlp 决定）
- 📋 **一键粘贴** — 自动读取剪贴板中的视频链接
- 🎬 **格式选择** — MP4 / WebM / MP3
- 📐 **画质选择** — 最佳 / 1080p / 720p / 仅音频
- 🔀 **代理策略** — 自动判断（YouTube 走代理，其余直连）/ 强制代理 / 强制直连
- 🍪 **Cookie 支持** — 浏览器 Cookie 导入 / cookies.txt 文件
- 📝 **智能命名** — 自动获取视频标题作为文件名，重名自动追加序号
- 📅 **日期归类** — 按"X月X日"自动创建子文件夹
- 📊 **实时进度条** — yt-dlp 输出解析，百分比实时更新
- 📜 **完整日志** — 下载日志实时显示在界面中
- 🔄 **核心更新** — 一键更新 yt-dlp.exe 到最新版

## 截图

> 运行后界面包含：视频链接输入、保存路径、格式/质量/代理选择、视频信息展示、进度条、日志区域。

## 环境要求

- **Python 3.10+**（使用了 `str | None` 类型注解语法）
- **Windows**（GUI 基于 tkinter，其他平台需安装 `python3-tk`）
- **yt-dlp.exe** — 核心下载引擎

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/your-username/VideoDL.git
cd VideoDL
```

### 2. 准备工具

创建 `tools/` 目录并放入 `yt-dlp.exe`（必需）和 `ffmpeg.exe`（可选）：

```
VideoDL/
├── tools/
│   ├── yt-dlp.exe      ← 必需，从 GitHub Releases 下载
│   └── ffmpeg.exe      ← 可选，用于合并视频/音频流
├── video_downloader.py
├── config.example.json
├── requirements.txt
└── README.md
```

- **yt-dlp.exe**：https://github.com/yt-dlp/yt-dlp/releases
- **ffmpeg.exe**：https://ffmpeg.org/download.html

> 💡 ffmpeg 也可以通过系统 PATH 提供（如已通过包管理器安装），程序会自动检测。

### 3. 运行

```bash
python video_downloader.py
```

首次运行会自动在脚本目录生成 `config.json`。你也可以复制 `config.example.json` 并重命名为 `config.json`，根据自己的环境修改路径。

### 4. 使用

1. 粘贴视频链接（或点击"一键粘贴"）
2. 选择格式（mp4 / webm / mp3）和画质
3. 点击"🚀 开始下载"
4. 完成后自动打开下载文件夹

## 配置说明

`config.json` 由程序自动管理，字段说明如下：

| 字段 | 类型 | 说明 |
|------|------|------|
| `save_dir` | string | 视频保存的根目录 |
| `proxy_mode` | string | `"auto"` 自动 / `"direct"` 直连 / `"proxy"` 强制代理 |
| `proxy_url` | string | 代理地址，默认 `http://127.0.0.1:7897` |
| `cookie_mode` | string | `"none"` 不使用 / `"file"` cookies.txt / `"browser"` 浏览器 |
| `cookie_path` | string | cookies.txt 文件路径 |
| `cookie_browser` | string | 浏览器名称：chrome / firefox / edge / opera / brave / safari |
| `default_format` | string | `"mp4"` / `"webm"` / `"mp3"` |
| `default_quality` | string | `"best"` / `"1080p"` / `"720p"` / `"audio"` |
| `auto_open_folder` | bool | 下载完成后是否自动打开文件夹 |

参考 `config.example.json`。

## 项目结构

```
VideoDL/
├── video_downloader.py    # 主程序（GUI + 下载逻辑）
├── config.example.json    # 示例配置文件
├── requirements.txt       # Python 依赖说明
├── .gitignore             # Git 忽略规则
├── LICENSE                # MIT 许可证
├── README.md              # 项目说明（本文件）
└── tools/                 # 外部可执行文件目录（需自行创建和下载）
    ├── yt-dlp.exe
    └── ffmpeg.exe
```

## 常见问题

### Q: 启动报错"未找到 yt-dlp.exe"
A: 请从 [yt-dlp Releases](https://github.com/yt-dlp/yt-dlp/releases) 下载 `yt-dlp.exe`，放入 `tools/` 目录。

### Q: 下载的视频没有声音 / 画音不同步
A: 需要 ffmpeg 来合并视频和音频流。将 `ffmpeg.exe` 放入 `tools/` 目录，或将 ffmpeg 加入系统 PATH。

### Q: YouTube 无法下载
A: 可能需要配置代理。在设置中将代理模式设为 `proxy`，并填入正确的代理地址（如 Clash/V2Ray 等）。

### Q: 需要登录才能看的视频
A: 在设置中切换 Cookie 模式为 `browser` 并选择浏览器（需先在浏览器中登录），或使用 `file` 模式导入 cookies.txt。

## 注意事项

- 本项目仅供学习和个人使用，请遵守相关平台的服务条款和当地法律法规。
- 请尊重版权，不要下载未经授权的内容。
- yt-dlp 和 ffmpeg 是各自所有者的商标/项目，与本项目无关。

## 许可证

MIT License — 详见 [LICENSE](LICENSE) 文件。
