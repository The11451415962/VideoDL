#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频下载器 GUI —— 基于 yt-dlp + tkinter
功能：粘贴链接 → 自动增量命名 → 异步下载 → 进度反馈 → 自动打开文件夹

项目地址：https://github.com/your-username/VideoDL
"""

import json
import os
import re
import shutil
import subprocess
import threading
import tkinter as tk
import queue
from tkinter import filedialog, ttk, messagebox
from datetime import datetime

from error_diagnosis import diagnose  # 下载失败诊断模块

# ============================================================
# 常量配置
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.join(SCRIPT_DIR, "tools")
YTDLP_PATH = os.path.join(TOOLS_DIR, "yt-dlp.exe")
FFMPEG_PATH = os.path.join(TOOLS_DIR, "ffmpeg.exe")

DEFAULT_CONFIG = {
    "save_dir": os.path.join(os.path.expanduser("~"), "Desktop", "VideoDL"),
    "proxy_mode": "auto",          # "auto" | "direct" | "proxy"
    "proxy_url": "http://127.0.0.1:7897",
    "cookie_mode": "none",         # "none" | "file" | "browser"
    "cookie_path": "",
    "cookie_browser": "chrome",
    "default_format": "mp4",       # "mp4" | "webm" | "mp3"
    "default_quality": "best",     # "best" | "1080p" | "720p" | "audio"
    "auto_open_folder": True,
}


def get_config_path() -> str:
    """返回 config.json 的完整路径（与脚本同目录）。"""
    return os.path.join(SCRIPT_DIR, "config.json")


def load_config() -> dict:
    """
    读取 config.json；兼容旧版（只有 save_dir）。
    缺失字段自动用 DEFAULT_CONFIG 补齐。
    如果 config.json 不存在，自动生成一份默认配置。
    """
    config = dict(DEFAULT_CONFIG)
    config_path = get_config_path()
    if os.path.isfile(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                config.update(data)
        except (json.JSONDecodeError, OSError):
            pass
    else:
        # 首次运行时自动生成 config.json
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except OSError:
            pass
    return config


def save_config(config: dict) -> None:
    """将完整 config 字典写入 config.json。"""
    config_path = get_config_path()
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


# ============================================================
# 工具函数
# ============================================================
def ensure_dir(path: str) -> None:
    """目录不存在则递归创建。"""
    if not os.path.isdir(path):
        os.makedirs(path)


def find_ffmpeg(config: dict) -> str | None:
    """
    查找 ffmpeg 可执行文件，按优先级：
      1. 用户在设置中指定的路径
      2. 项目 tools/ 目录下的 ffmpeg.exe
      3. 系统 PATH 中已安装的 ffmpeg
    返回路径或 None。
    """
    # 1. 用户配置的路径
    user_path = config.get("ffmpeg_path", "")
    if user_path and os.path.isfile(user_path):
        return user_path

    # 2. 项目自带的 ffmpeg.exe
    if os.path.isfile(FFMPEG_PATH):
        return FFMPEG_PATH

    # 3. 系统 PATH
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg

    return None


def check_ytdlp() -> str | None:
    """
    检查 yt-dlp.exe 是否存在。返回错误信息，正常则返回 None。
    """
    if not os.path.isfile(YTDLP_PATH):
        return (
            "未找到 yt-dlp.exe，请将其放入 tools/ 目录。\n"
            "下载地址：https://github.com/yt-dlp/yt-dlp/releases\n"
            f"期望路径：{YTDLP_PATH}"
        )
    return None


def check_ffmpeg(config: dict) -> str | None:
    """
    检查 ffmpeg 是否可用。返回警告信息（缺失时），正常则返回 None。
    仅作提醒，不阻止下载（无 ffmpeg 时 yt-dlp 仍可下载，但无法合并格式）。
    """
    ffmpeg = find_ffmpeg(config)
    if ffmpeg is None:
        return (
            "未找到 ffmpeg，将无法合并视频/音频流（不影响单独下载）。\n"
            "建议：将 ffmpeg.exe 放入 tools/ 目录，或将 ffmpeg 加入系统 PATH。\n"
            "下载地址：https://ffmpeg.org/download.html"
        )
    return None


# ============================================================
# 主题 / 样式（全局配色、字体与 ttk 风格）
# ============================================================
COLORS = {
    "bg": "#f4f6fb",            # 窗口背景
    "surface": "#ffffff",       # 卡片表面
    "border": "#e3e8f0",        # 边框
    "primary": "#4f6ef7",       # 主色（强调蓝）
    "primary_hover": "#3f5ae0",
    "primary_bg": "#eef2ff",    # 主色浅底
    "text": "#1f2430",          # 主文字
    "muted": "#6b7280",         # 次要文字
    "success": "#16a34a",
    "error": "#dc2626",
    "warn": "#d97706",
    "trough": "#e9edf5",        # 进度条槽
    "log_bg": "#fbfcfe",        # 日志框底色
}

FONT_UI = ("Microsoft YaHei UI", 10)
FONT_UI_BOLD = ("Microsoft YaHei UI", 10, "bold")
FONT_TITLE = ("Microsoft YaHei UI", 15, "bold")
FONT_SUB = ("Microsoft YaHei UI", 9)
FONT_MONO = ("Consolas", 9)


def apply_theme(root) -> None:
    """为窗口/对话框应用统一的现代化扁平主题（基于 clam 主题定制）。"""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    root.configure(bg=COLORS["bg"])

    # ---- 全局默认 ----
    style.configure(".", font=FONT_UI, background=COLORS["bg"], foreground=COLORS["text"])
    style.configure("TFrame", background=COLORS["bg"])

    # ---- 卡片 ----
    style.configure("Card.TFrame", background=COLORS["surface"])
    style.configure("Card.TLabel", background=COLORS["surface"], foreground=COLORS["text"])
    style.configure("CardTitle.TLabel", background=COLORS["surface"],
                    foreground=COLORS["text"], font=FONT_UI_BOLD)
    style.configure("Hint.TLabel", background=COLORS["surface"],
                    foreground=COLORS["muted"], font=FONT_SUB)
    style.configure("Info.TLabel", background=COLORS["surface"],
                    foreground=COLORS["text"], font=FONT_UI)
    style.configure("Field.TLabel", background=COLORS["surface"],
                    foreground=COLORS["muted"], font=FONT_UI)

    # ---- LabelFrame ----
    style.configure("TLabelframe", background=COLORS["bg"],
                    bordercolor=COLORS["border"], relief="solid")
    style.configure("TLabelframe.Label", background=COLORS["bg"],
                    foreground=COLORS["text"], font=FONT_UI_BOLD)

    # ---- Entry ----
    style.configure("TEntry", fieldbackground=COLORS["surface"], background=COLORS["surface"],
                    foreground=COLORS["text"], bordercolor=COLORS["border"],
                    lightcolor=COLORS["border"], darkcolor=COLORS["border"],
                    insertcolor=COLORS["text"], padding=6)
    style.map("TEntry",
              bordercolor=[("focus", COLORS["primary"])],
              lightcolor=[("focus", COLORS["primary"])],
              darkcolor=[("focus", COLORS["primary"])])

    # ---- Combobox ----
    style.configure("TCombobox", fieldbackground=COLORS["surface"], background=COLORS["surface"],
                    foreground=COLORS["text"], bordercolor=COLORS["border"],
                    arrowcolor=COLORS["muted"], padding=4)
    style.map("TCombobox",
              bordercolor=[("focus", COLORS["primary"])],
              lightcolor=[("focus", COLORS["primary"])],
              darkcolor=[("focus", COLORS["primary"])])
    root.option_add("*TCombobox*Listbox.background", COLORS["surface"])
    root.option_add("*TCombobox*Listbox.foreground", COLORS["text"])
    root.option_add("*TCombobox*Listbox.selectBackground", COLORS["primary"])
    root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

    # ---- 普通按钮 ----
    style.configure("TButton", background=COLORS["surface"], foreground=COLORS["text"],
                    bordercolor=COLORS["border"], lightcolor=COLORS["border"],
                    darkcolor=COLORS["border"], padding=(10, 6),
                    focusthickness=0, relief="flat")
    style.map("TButton",
              background=[("disabled", "#eef1f7"), ("pressed", "#e6eaf2"), ("active", "#f0f3fa")],
              foreground=[("disabled", "#a3abb8")],
              bordercolor=[("focus", COLORS["primary"])])

    # ---- 主按钮（强调色） ----
    style.configure("Accent.TButton", background=COLORS["primary"], foreground="#ffffff",
                    bordercolor=COLORS["primary"], lightcolor=COLORS["primary"],
                    darkcolor=COLORS["primary"], padding=(16, 8), font=FONT_UI_BOLD)
    style.map("Accent.TButton",
              background=[("disabled", "#b6c1f7"), ("pressed", COLORS["primary_hover"]),
                          ("active", COLORS["primary_hover"])],
              foreground=[("disabled", "#f0f3ff")])

    # ---- 次级按钮 ----
    style.configure("Secondary.TButton", background=COLORS["primary_bg"], foreground=COLORS["primary"],
                    bordercolor=COLORS["primary_bg"], lightcolor=COLORS["primary_bg"],
                    darkcolor=COLORS["primary_bg"], padding=(10, 6), font=FONT_UI_BOLD)
    style.map("Secondary.TButton",
              background=[("disabled", "#eef1f7"), ("pressed", "#dfe6ff"), ("active", "#e3e9ff")],
              foreground=[("disabled", "#a3abb8")])

    # ---- 进度条 ----
    style.configure("Horizontal.TProgressbar", background=COLORS["primary"],
                    troughcolor=COLORS["trough"], bordercolor=COLORS["trough"],
                    lightcolor=COLORS["primary"], darkcolor=COLORS["primary"], thickness=10)

    # ---- 复选框 / 滚动条 ----
    style.configure("TCheckbutton", background=COLORS["surface"], foreground=COLORS["text"])
    style.map("TCheckbutton", background=[("active", COLORS["surface"])])
    style.configure("Vertical.TScrollbar", background=COLORS["border"],
                    troughcolor=COLORS["bg"], bordercolor=COLORS["bg"], arrowcolor=COLORS["muted"])


def make_card(parent, pad=(14, 12, 14, 12), **pack):
    """创建一个卡片（圆角边框白底），返回用于放入控件的内层 Frame。

    用法：inner = make_card(parent, pady=(0, 10)); 往 inner 里加控件。
    """
    card = tk.Frame(parent, bg=COLORS["surface"], bd=0,
                    highlightbackground=COLORS["border"], highlightcolor=COLORS["primary"],
                    highlightthickness=1)
    inner = ttk.Frame(card, style="Card.TFrame", padding=pad)
    inner.pack(fill=tk.BOTH, expand=True)
    card.pack(**pack)
    return inner


def card_title(parent, text: str) -> None:
    """在卡片内添加小节标题。"""
    ttk.Label(parent, text=text, style="CardTitle.TLabel").pack(anchor="w")


# --------------- 平台检测 ---------------
def detect_platform(url: str) -> str:
    """根据 URL 返回平台名称。"""
    u = url.lower()
    if "youtube.com" in u or "youtu.be" in u:
        return "YouTube"
    if "bilibili.com" in u or "b23.tv" in u:
        return "Bilibili"
    if "douyin.com" in u or "tiktok.com" in u:
        return "抖音"
    return "未知"


# --------------- 代理决策 ---------------
def resolve_proxy(config: dict, url: str) -> str | None:
    """
    根据 config["proxy_mode"] 决定是否使用代理：
      - "direct"  → 不使用
      - "proxy"   → 使用 config["proxy_url"]
      - "auto"    → YouTube 走代理，其余直连
    返回代理 URL 或 None。
    """
    mode = config.get("proxy_mode", "auto")
    if mode == "direct":
        return None
    if mode == "proxy":
        return config.get("proxy_url", "http://127.0.0.1:7897")
    # auto
    if detect_platform(url) == "YouTube":
        return config.get("proxy_url", "http://127.0.0.1:7897")
    return None


# --------------- 格式 / 质量 → yt-dlp format string ---------------
def resolve_format_string(fmt: str, quality: str, platform: str = "未知") -> list[str]:
    """
    返回 yt-dlp 的 --format / --merge-output-format 参数列表。

    兼容优先 —— 手机相册 / 剪映(CapCut) 这类 App 只认 H.264 + AAC。
    实测 B 站同一个分辨率下同时提供三种编码，yt-dlp 默认按"编码越新越优先"排序
    会挑 av01（AV1）：
        1080P → avc1 3378k / hvc1 1112k / av01 1074k（默认选中）
        720P  → avc1 1556k / hvc1  565k / av01  532k（默认选中）
    结果就是"后缀是 .mp4、里面是 AV1"，剪映报不支持，用户被迫去在线转码。
    （旧版还额外踩了一个坑：YouTube 用 [ext=mp4] 过滤，而 YouTube 的 AV1 流
      同样是 mp4 容器，所以那条路也一样会选到 AV1。）

    因此统一改为：优先 avc1 + mp4a，挑不到才逐级放宽。
    platform 参数保留是为了兼容调用方，当前策略已不分平台。
    """
    # 仅音频
    if fmt == "mp3" or quality == "audio":
        return ["-f", "bestaudio/best", "--audio-format", "mp3"]

    height = {"1080p": "[height<=1080]", "720p": "[height<=720]"}.get(quality, "")

    if fmt == "webm":
        selector = (f"bestvideo{height}[ext=webm]+bestaudio[ext=webm]"
                    f"/best{height}[ext=webm]/best")
        return ["-f", selector, "--merge-output-format", "webm"]

    # mp4：H.264 + AAC 逐级回退（第一个能被匹配到的优先）
    selector = "/".join([
        f"bestvideo{height}[vcodec^=avc1]+bestaudio[acodec^=mp4a]",
        f"bestvideo{height}[vcodec^=avc1]+bestaudio",
        f"best[ext=mp4]{height}[vcodec^=avc1]",
        f"best[ext=mp4]{height}",
        f"bestvideo{height}+bestaudio",
        f"best{height}",
    ])
    return ["-f", selector, "--merge-output-format", "mp4"]


def output_ext(fmt: str, quality: str) -> str:
    """返回实际输出文件扩展名；audio 画质总是产出 mp3。"""
    return "mp3" if (fmt == "mp3" or quality == "audio") else fmt


# Windows 保留设备名：以这些名字命名的文件会创建失败
_WIN_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def safe_filename(title: str, max_len: int = 120) -> str:
    """把视频标题变成能在 Windows/安卓上安全落盘的文件名。

    旧实现只替换了非法字符，漏掉了三类会让写入直接失败或超长的情况：
      · 结尾的点和空格（Windows 不允许）
      · 保留设备名（CON/NUL/COM1…）
      · 控制字符与超长（含路径可能超过 MAX_PATH）
    """
    name = re.sub(r'[\\/:*?"<>|]', "_", title or "")
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)
    name = name.strip().rstrip(". ")
    if not name:
        return "video"
    # 保留名带扩展名同样被 Windows 拒绝（NUL.mp4 也不行），所以取第一段判断
    if name.split(".")[0].upper() in _WIN_RESERVED:
        name = f"_{name}"
    name = name[:max_len].rstrip(". ")
    return name or "video"


# --------------- yt-dlp 命令组装 ---------------
def build_ytdlp_command(url: str, output_path: str, config: dict,
                        ffmpeg_path: str | None = None) -> list[str]:
    """
    根据 config 组装完整的 yt-dlp 命令行参数列表。
    """
    fmt = config.get("default_format", "mp4")
    quality = config.get("default_quality", "best")

    platform = detect_platform(url)
    # 注意顺序：所有选项必须在 "--" 之前，URL 必须紧跟在 "--" 之后。
    # 反过来写会把 -o/--newline 这些也当成 URL（实测直接把下载搞崩）。
    # 这样手输的 "-U"/"--exec ..." 之类字符串不会被当选项执行（CWE-88 参数注入）。
    cmd = ["-o", output_path]
    cmd.extend(resolve_format_string(fmt, quality, platform))

    # Bilibili 需要 Referer + Origin 请求头，否则 CDN 返回 HTTP 412
    if platform == "Bilibili":
        cmd.extend([
            "--add-header", "Referer:https://www.bilibili.com/",
            "--add-header", "Origin:https://www.bilibili.com",
        ])

    # 代理
    proxy = resolve_proxy(config, url)
    if proxy:
        cmd.extend(["--proxy", proxy])

    # Cookie
    cookie_mode = config.get("cookie_mode", "none")
    if cookie_mode == "file":
        cookie_path = config.get("cookie_path", "")
        if cookie_path and os.path.isfile(cookie_path):
            cmd.extend(["--cookies", cookie_path])
    elif cookie_mode == "browser":
        browser = config.get("cookie_browser", "chrome")
        cmd.extend(["--cookies-from-browser", browser])

    # FFmpeg
    if ffmpeg_path and os.path.isfile(ffmpeg_path):
        cmd.extend(["--ffmpeg-location", ffmpeg_path])

    cmd.extend(["--newline", "--no-playlist", "--playlist-items", "1"])
    # URL 走最后，用 "--" 隔断选项解析
    cmd.extend(["--", url])
    return [YTDLP_PATH] + cmd


def get_today_folder(base_dir: str) -> tuple[str, str]:
    """
    按系统当前日期 + 用户选定的基础目录动态生成：
        - 文件夹名（如 "6月15日"）
        - 完整路径（如 C:/.../VideoDL/6月15日/）

    绝不硬编码任何日期。
    """
    now = datetime.now()
    folder_name = f"{now.month}月{now.day}日"
    full_path = os.path.join(base_dir, folder_name)
    return folder_name, full_path


def get_next_filepath(target_dir: str, base_name: str, ext: str = "webm") -> str:
    """
    在 target_dir 下，以 base_name 为基础，使用 os.path.exists 探测重名，
    返回不冲突的完整文件路径：

        base_name.mp4  →  base_name(2).mp4  →  base_name(3).mp4  ...
    """
    idx = 1
    while True:
        name = f"{base_name}.{ext}" if idx == 1 else f"{base_name}({idx}).{ext}"
        full = os.path.join(target_dir, name)
        if not os.path.exists(full):
            return full
        idx += 1


def extract_url_from_text(text: str) -> str | None:
    """从文本中提取第一个 URL；若文本本身就是链接则原样返回。

    供两个界面共用（tkinter 版通过 App._extract_url_from_text 调用，
    Qt 版直接调用本函数，避免去访问 App 的私有实例方法）。
    """
    text = (text or "").strip()
    if not text:
        return None
    if text.lower().startswith("http"):
        return text.rstrip('。．.，,/\\')
    # 适配抖音分享文本："复制打开抖音，看看【xxx】''标题... https://v.douyin.com/xxxxx/ ..."
    match = re.search(r'https?://[^\s]+', text)
    if match:
        return match.group(0).rstrip('。．.，,/\\')
    return None


# ============================================================
# 启动辅助函数（隐藏 Windows 控制台黑框）
# ============================================================
def _startupinfo():
    """返回 subprocess startupinfo，Windows 下隐藏 CMD 黑框。"""
    if os.name == "nt":
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        return si
    return None


# ============================================================
# 兼容性兜底（H.264 + AAC）—— 与安卓版 ytdlp_bridge.py 同一套逻辑
# ------------------------------------------------------------
# 格式选择已经优先挑 avc1 + mp4a 了，但有些清晰度只提供 HEVC/AV1
# （例如 B 站 1080P+ / 4K）。这时把它命名成 .mp4 是骗人的：剪映、相册
# 打开就报"不支持的格式"，用户只能去在线转码平台。这里真转一遍。
# ============================================================
def _ffprobe_path(ffmpeg_path: str | None) -> str | None:
    """推导 ffprobe 路径：与 ffmpeg 同目录，兼容 .exe 与安卓的 libffprobe.so。"""
    if not ffmpeg_path:
        return None
    d = os.path.dirname(ffmpeg_path)
    base = os.path.basename(ffmpeg_path)
    cands = []
    if base.endswith(".so"):
        cands.append(os.path.join(d, base.replace("ffmpeg", "ffprobe")))
    cands += [
        os.path.join(d, base.replace("ffmpeg", "ffprobe")),
        os.path.join(d, "ffprobe.exe"),
        os.path.join(d, "ffprobe"),
    ]
    for p in cands:
        if p and os.path.isfile(p):
            return p
    return None


def probe_codecs(path: str, ffmpeg_path: str | None) -> tuple[str | None, str | None, float]:
    """返回 (vcodec, acodec, duration)；探测失败返回 (None, None, 0)。"""
    ffprobe = _ffprobe_path(ffmpeg_path)
    if not ffprobe:
        return None, None, 0.0
    try:
        out = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries",
             "stream=codec_type,codec_name:format=duration",
             "-of", "json", path],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=60, startupinfo=_startupinfo(),
        )
        data = json.loads((out.stdout or b"{}").decode("utf-8", "replace"))
    except Exception:
        return None, None, 0.0
    vcodec = acodec = None
    for st in data.get("streams", []):
        if st.get("codec_type") == "video" and vcodec is None:
            vcodec = (st.get("codec_name") or "").lower()
        elif st.get("codec_type") == "audio" and acodec is None:
            acodec = (st.get("codec_name") or "").lower()
    try:
        duration = float(data.get("format", {}).get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0.0
    return vcodec, acodec, duration


def _run_transcode(ffmpeg_path, src, tmp, extra, total, progress_cb, cancel_check):
    """跑一次转码，返回 (返回码, 尾部输出)。rc == -1 表示用户取消。"""
    cmd = [ffmpeg_path, "-y", "-hide_banner", "-loglevel", "error",
           "-i", src,
           "-c:v", "libx264", "-preset", "veryfast",
           # 只限制"超过 1080P"的情况：再高的分辨率转码太慢、手机剪辑也用不上
           "-vf", "scale=-2:'min(1080,ih)'",
           "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k",
           "-movflags", "+faststart"] + list(extra) + [tmp]
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            bufsize=1, startupinfo=_startupinfo(),
        )
    except Exception as e:
        return 127, [f"无法启动 ffmpeg: {e}"]

    tail: list[str] = []
    try:
        for line in proc.stdout:
            if cancel_check and cancel_check():
                proc.kill()
                return -1, ["cancelled"]
            line = line.strip()
            if line.startswith("out_time_ms=") and total > 0 and progress_cb:
                try:
                    done_s = int(line.split("=", 1)[1]) / 1_000_000.0
                    progress_cb(max(0.0, min(99.0, done_s / total * 100.0)))
                except ValueError:
                    pass
            elif line and not line.startswith(("frame=", "fps=", "bitrate=",
                                               "total_size=", "out_time",
                                               "dup_frames=", "drop_frames=",
                                               "speed=", "progress=")):
                tail.append(line)
                del tail[:-6]
        proc.wait(timeout=30)
    except Exception as e:
        tail.append(f"转码异常: {e}")
    finally:
        try:
            proc.stdout.close()
        except Exception:
            pass
    return proc.returncode, tail


def ensure_importable(path: str, ffmpeg_path: str | None, duration: float = 0,
                      log_cb=print, progress_cb=None,
                      cancel_check=None) -> tuple[bool, str]:
    """确保文件真的能被手机相册 / 剪映导入。返回 (ok, reason)。"""
    if not os.path.isfile(path):
        return True, ""
    vcodec, acodec, probed = probe_codecs(path, ffmpeg_path)
    if vcodec is None:
        log_cb("[提示] 读不到编码信息，跳过兼容性检查")
        return True, ""
    if vcodec == "h264" and acodec in ("aac", None, ""):
        return True, ""
    if not ffmpeg_path or not os.path.isfile(ffmpeg_path):
        log_cb(f"[警告] 视频编码是 {vcodec}/{acodec}，剪映等 App 可能不支持；"
               f"未找到 ffmpeg，无法自动转码")
        return False, f"codec={vcodec}/{acodec}"

    total = duration or probed or 0
    log_cb(f"[提示] 视频编码是 {vcodec}（剪映不支持），正在转成 H.264 + AAC…")
    tmp = path + ".compat.mp4"
    attempts = [
        (["-crf", "20", "-progress", "pipe:1", "-nostats"], "crf + 进度"),
        (["-b:v", "4000k"], "固定码率降级"),
    ]
    for extra, desc in attempts:
        if cancel_check and cancel_check():
            return False, "cancelled"
        if os.path.isfile(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        rc, tail = _run_transcode(ffmpeg_path, path, tmp, extra, total,
                                  progress_cb, cancel_check)
        if rc == -1:
            log_cb("[提示] 已取消转码")
            return False, "cancelled"
        if rc == 0 and os.path.isfile(tmp):
            try:
                os.replace(tmp, path)
            except OSError as e:
                log_cb(f"[警告] 转码结果写入失败：{e}")
                return False, str(e)
            log_cb("[完成] 已转成 H.264 + AAC，手机相册 / 剪映可直接导入")
            return True, ""
        log_cb(f"[警告] 转码失败（{desc}）：{' | '.join(tail)[:200]}")

    log_cb("[警告] 两种参数都失败，已保留原文件；可改用较低清晰度重下（1080P 一般是 H.264）")
    return False, "transcode-failed"


# ============================================================
# 下载器（独立线程运行）
# ============================================================
class Downloader:
    """异步下载器 —— 先获取视频信息，再下载。"""

    def __init__(self, url: str, output_path: str, config: dict,
                 ffmpeg_path: str | None,
                 info_cb, progress_cb, done_cb, log_cb, error_cb=None):
        self.url = url
        self.output_path = output_path
        self.config = config
        self.ffmpeg_path = ffmpeg_path
        self.info_cb = info_cb        # (dict)
        self.progress_cb = progress_cb  # (float)
        self.done_cb = done_cb          # (bool, str)
        self.log_cb = log_cb            # (str)
        self.error_cb = error_cb      # (dict) 诊断报告回调
        self._proc = None
        self._output_lines: list[str] = []  # 收集输出用于诊断
        self._cancelled = False              # 用户主动取消标志
        self._duration = 0                   # 视频时长（转码进度用）

    def run(self) -> None:
        """主流程：抓信息 → 下载"""
        err = check_ytdlp()
        if err:
            self.log_cb(f"[错误] {err}")
            self.done_cb(False, "找不到 yt-dlp.exe")
            return

        # 阶段 1：获取视频信息
        info = self._fetch_info()
        if info:
            try:
                self._duration = int(info.get("duration") or 0)
            except (TypeError, ValueError):
                self._duration = 0
            # 用标题同步重建输出路径（必须在 _download 之前，否则与下载线程竞态）
            self._apply_title_path(info)
            self.info_cb(info)

        # 阶段 2：下载
        self._download()

    def _apply_title_path(self, info: dict) -> None:
        """下载前用视频标题同步重建输出路径，避免与下载线程的竞态。"""
        title = info.get("title")
        if not title:
            return
        safe_title = safe_filename(title)
        if not safe_title:
            return
        target_dir = os.path.dirname(self.output_path)
        ext = output_ext(
            self.config.get("default_format", "mp4"),
            self.config.get("default_quality", "best"),
        )
        self.output_path = get_next_filepath(target_dir, safe_title, ext=ext)

    def _fetch_info(self) -> dict | None:
        """用 yt-dlp --dump-json 获取视频元数据。"""
        self.log_cb("[信息] 正在获取视频信息...")
        platform = detect_platform(self.url)
        cmd = [
            "--dump-json",
            "--no-playlist", "--playlist-items", "1",
        ]
        # Bilibili 需要 Referer + Origin 请求头，否则 CDN 返回 HTTP 412
        if platform == "Bilibili":
            cmd.extend([
                "--add-header", "Referer:https://www.bilibili.com/",
                "--add-header", "Origin:https://www.bilibili.com",
            ])
        proxy = resolve_proxy(self.config, self.url)
        if proxy:
            cmd.extend(["--proxy", proxy])

        # Cookie（与下载步骤保持一致，否则抖音等平台获取信息就会失败）
        cookie_mode = self.config.get("cookie_mode", "none")
        if cookie_mode == "file":
            cookie_path = self.config.get("cookie_path", "")
            if cookie_path and os.path.isfile(cookie_path):
                cmd.extend(["--cookies", cookie_path])
        elif cookie_mode == "browser":
            browser = self.config.get("cookie_browser", "chrome")
            cmd.extend(["--cookies-from-browser", browser])

        # 选项在前、URL 最后，用 "--" 隔断（同 build_ytdlp_command）
        cmd.extend(["--", self.url])

        si = _startupinfo()
        try:
            proc = subprocess.Popen(
                [YTDLP_PATH] + cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace", startupinfo=si,
            )
            self._proc = proc
            out, err = proc.communicate(timeout=60)
            self._proc = None
            if proc.returncode != 0:
                self.log_cb(f"[警告] 获取信息失败：{err[:200]}")
                return None
            data = json.loads(out)
            info = {
                "title": data.get("title", "未知标题"),
                "uploader": data.get("uploader", data.get("channel", "未知")),
                "duration": data.get("duration", 0),
                "resolution": f'{data.get("width", "?")}x{data.get("height", "?")}',
                "platform": detect_platform(self.url),
                "thumbnail": data.get("thumbnail", "") or "",
                "filesize": data.get("filesize") or data.get("filesize_approx") or 0,
            }
            self.log_cb(f"[信息] 获取成功：{info['title']}")
            return info
        except subprocess.TimeoutExpired:
            # communicate 超时不会结束子进程，需手动清理，否则残留孤儿进程
            if self._proc is not None and self._proc.poll() is None:
                try:
                    self._proc.kill()
                except OSError:
                    pass
            self._proc = None
            self.log_cb("[警告] 获取信息超时（60 秒）")
            return None
        except Exception as e:
            self._proc = None
            self.log_cb(f"[警告] 获取信息异常：{e}")
            return None

    def _download(self) -> None:
        """执行 yt-dlp 下载并捕获输出。"""
        self.log_cb("[下载] 开始下载...")
        cmd = build_ytdlp_command(
            self.url, self.output_path, self.config, self.ffmpeg_path,
        )

        si = _startupinfo()
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",      # 中文标题/emoji 不会再让读取线程抛解码异常
                bufsize=1,
                startupinfo=si,
            )
        except Exception as e:
            self.done_cb(False, f"启动 yt-dlp 失败：{e}")
            return

        pattern = re.compile(r"\[download\]\s+(\d+\.?\d*)%")
        last_pct = -1.0
        rc = -1

        # 整个读取过程必须有 try/finally：否则一旦读输出出错，工作线程会静默死掉，
        # done_cb 永不触发 → 按钮全灰、"停止下载"一直亮着，只能重启程序。
        try:
            for line in self._proc.stdout:
                line_stripped = line.strip()
                if line_stripped:
                    self.log_cb(line_stripped)
                    self._output_lines.append(line_stripped)  # 收集用于诊断
                m = pattern.search(line_stripped) if line_stripped else None
                if m:
                    try:
                        pct = float(m.group(1))
                    except ValueError:
                        continue
                    if abs(pct - last_pct) > 0.01:
                        last_pct = pct
                        self.progress_cb(pct)
            rc = self._proc.wait()
        except Exception as e:
            self.log_cb(f"[错误] 读取下载输出失败：{e}")
            rc = -1
        finally:
            proc, self._proc = self._proc, None
            if proc is not None:
                try:
                    if proc.poll() is None:
                        proc.kill()
                except Exception:
                    pass
                for stream in (proc.stdout, proc.stderr):
                    try:
                        if stream is not None:
                            stream.close()
                    except Exception:
                        pass

        if self._cancelled:
            # 用户主动停止，不弹错误诊断框
            self.done_cb(False, "已停止下载")
            return

        if rc == 0:
            # 下载成功后再确认编码真的能被剪映/相册吃下（必要时就地转码）
            ok, reason = ensure_importable(
                self.output_path, self.ffmpeg_path, self._duration,
                log_cb=self.log_cb, progress_cb=self.progress_cb,
                cancel_check=lambda: self._cancelled,
            )
            if reason == "cancelled":
                self.done_cb(False, "已停止下载")
                return
            self.progress_cb(100.0)
            self.done_cb(True, "下载完成！")
        else:
            self.log_cb(f"[错误] yt-dlp 退出码：{rc}")
            # 生成诊断报告并回调
            if self.error_cb:
                try:
                    report = diagnose(self._output_lines)
                    self.error_cb(report)
                except Exception as e:
                    self.log_cb(f"[警告] 生成诊断报告失败：{e}")
            self.done_cb(False, f"下载失败，退出码：{rc}")

    def cancel(self):
        """终止下载。"""
        self._cancelled = True
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            self.log_cb("[用户] 已停止下载")


# ============================================================
# 更新器（后台线程）
# ============================================================
def update_ytdlp(callback):
    """后台执行 yt-dlp -U，完成后通过 callback(str) 通知。"""
    if not os.path.isfile(YTDLP_PATH):
        callback("找不到 yt-dlp.exe，无法更新。")
        return

    proc = None
    try:
        proc = subprocess.Popen(
            [YTDLP_PATH, "-U"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            startupinfo=_startupinfo(),
        )
        out, _ = proc.communicate(timeout=120)
        if proc.returncode == 0:
            callback(f"更新成功！\n{out.strip()[-300:]}")
        else:
            callback(f"更新失败（退出码 {proc.returncode}）\n{out.strip()[-300:]}")
    except subprocess.TimeoutExpired:
        # 超时后必须收掉子进程：否则留下孤儿进程，按钮也会一直是"更新中…"
        if proc is not None and proc.poll() is None:
            try:
                proc.kill()
            except OSError:
                pass
        callback("更新超时（网络慢时 -U 可能超过 2 分钟），请稍后重试。")
    except Exception as e:
        if proc is not None and proc.poll() is None:
            try:
                proc.kill()
            except OSError:
                pass
        callback(f"更新出错：{e}")


# ============================================================
# 设置对话框
# ============================================================
class SettingsDialog(tk.Toplevel):
    """设置对话框 —— 代理 / Cookie / FFmpeg / 其他。"""

    def __init__(self, parent, config: dict, on_save):
        super().__init__(parent)
        self.title("设置")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.config = dict(config)  # 副本，取消不写入
        self._on_save = on_save

        apply_theme(self)
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        # 先隐藏 → 等窗口真正渲染 → 居中 → 再显示，避免在左上角闪一下
        self.withdraw()
        self.update_idletasks()
        self._center_on_parent(parent)
        self.deiconify()

    def _build_ui(self):
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)

        # ---- 代理设置 ----
        proxy_frame = ttk.LabelFrame(frame, text="代理设置", padding=8)
        proxy_frame.pack(fill=tk.X, pady=(0, 8))

        row_p = ttk.Frame(proxy_frame)
        row_p.pack(fill=tk.X)
        ttk.Label(row_p, text="模式：").pack(side=tk.LEFT)
        self.proxy_mode_var = tk.StringVar(value=self._label_for_proxy(self.config["proxy_mode"]))
        self.cb_proxy_mode = ttk.Combobox(
            row_p, textvariable=self.proxy_mode_var,
            values=["auto (自动判断)", "direct (强制直连)", "proxy (强制代理)"],
            state="readonly", width=20,
        )
        self.cb_proxy_mode.pack(side=tk.LEFT, padx=(4, 12))
        ttk.Label(row_p, text="地址：").pack(side=tk.LEFT)
        self.proxy_url_var = tk.StringVar(value=self.config["proxy_url"])
        self.entry_proxy_url = ttk.Entry(
            row_p, textvariable=self.proxy_url_var, width=28,
        )
        self.entry_proxy_url.pack(side=tk.LEFT, padx=(4, 0))

        # ---- Cookie 设置 ----
        cookie_frame = ttk.LabelFrame(frame, text="Cookie 设置", padding=8)
        cookie_frame.pack(fill=tk.X, pady=(0, 8))

        row_c = ttk.Frame(cookie_frame)
        row_c.pack(fill=tk.X)
        ttk.Label(row_c, text="模式：").pack(side=tk.LEFT)
        self.cookie_mode_var = tk.StringVar(value=self._label_for_cookie(self.config["cookie_mode"]))
        self.cb_cookie = ttk.Combobox(
            row_c, textvariable=self.cookie_mode_var,
            values=["none (不使用)", "file (cookies.txt)", "browser (浏览器)"],
            state="readonly", width=20,
        )
        self.cb_cookie.pack(side=tk.LEFT, padx=(4, 0))
        self.cb_cookie.bind("<<ComboboxSelected>>", self._on_cookie_mode_change)

        # Cookie 文件行（动态显示）
        self.cookie_file_row = ttk.Frame(cookie_frame)
        ttk.Label(self.cookie_file_row, text="文件：").pack(side=tk.LEFT)
        self.cookie_path_var = tk.StringVar(value=self.config.get("cookie_path", ""))
        self.entry_cookie_path = ttk.Entry(
            self.cookie_file_row, textvariable=self.cookie_path_var, width=36,
        )
        self.entry_cookie_path.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 4))
        self.btn_cookie_browse = ttk.Button(
            self.cookie_file_row, text="📁",
            command=lambda: self._browse_file(self.cookie_path_var),
        )
        self.btn_cookie_browse.pack(side=tk.LEFT)

        # Cookie 浏览器行（动态显示）
        self.cookie_browser_row = ttk.Frame(cookie_frame)
        ttk.Label(self.cookie_browser_row, text="浏览器：").pack(side=tk.LEFT)
        self.cookie_browser_var = tk.StringVar(
            value=self.config.get("cookie_browser", "chrome"),
        )
        self.cb_browser = ttk.Combobox(
            self.cookie_browser_row, textvariable=self.cookie_browser_var,
            values=["chrome", "firefox", "edge", "opera", "brave", "safari"],
            state="readonly", width=14,
        )
        self.cb_browser.pack(side=tk.LEFT, padx=(4, 0))

        self._on_cookie_mode_change()  # 初始显示状态

        # ---- 其他设置 ----
        other_frame = ttk.LabelFrame(frame, text="其他", padding=8)
        other_frame.pack(fill=tk.X, pady=(0, 12))

        self.auto_open_var = tk.BooleanVar(value=self.config.get("auto_open_folder", True))
        ttk.Checkbutton(
            other_frame, text="下载完成后自动打开文件夹",
            variable=self.auto_open_var,
        ).pack(anchor=tk.W)

        ffmpeg_row = ttk.Frame(other_frame)
        ffmpeg_row.pack(fill=tk.X, pady=(6, 0))
        ttk.Label(ffmpeg_row, text="FFmpeg 路径：").pack(side=tk.LEFT)
        ffmpeg_default = self.config.get("ffmpeg_path", FFMPEG_PATH)
        if not os.path.isfile(ffmpeg_default):
            ffmpeg_default = FFMPEG_PATH if os.path.isfile(FFMPEG_PATH) else ""
        self.ffmpeg_path_var = tk.StringVar(value=ffmpeg_default)
        self.entry_ffmpeg_path = ttk.Entry(
            ffmpeg_row, textvariable=self.ffmpeg_path_var, width=36,
        )
        self.entry_ffmpeg_path.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 4))
        ttk.Button(
            ffmpeg_row, text="📁",
            command=lambda: self._browse_ffmpeg(),
        ).pack(side=tk.LEFT)

        # ---- 底部按钮 ----
        btn_row = ttk.Frame(frame)
        btn_row.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(btn_row, text="保存", style="Accent.TButton",
                   command=self._on_save_click).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(btn_row, text="取消", command=self._on_cancel).pack(side=tk.RIGHT)

    # --------------- Cookie 模式切换 ---------------
    def _on_cookie_mode_change(self, event=None):
        mode = self._cookie_raw()
        self.cookie_file_row.pack_forget()
        self.cookie_browser_row.pack_forget()
        if mode == "file":
            self.cookie_file_row.pack(fill=tk.X, pady=(6, 0))
        elif mode == "browser":
            self.cookie_browser_row.pack(fill=tk.X, pady=(6, 0))

    # --------------- 文件浏览 ---------------
    def _browse_file(self, var: tk.StringVar):
        path = filedialog.askopenfilename(
            title="选择 cookies.txt 文件",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if path:
            var.set(path)

    def _browse_ffmpeg(self):
        path = filedialog.askopenfilename(
            title="选择 ffmpeg 可执行文件",
            filetypes=[("ffmpeg", "ffmpeg.exe"), ("All files", "*.*")],
        )
        if path:
            self.ffmpeg_path_var.set(path)

    # --------------- 标签 ↔ 值 ---------------
    @staticmethod
    def _label_for_proxy(raw: str) -> str:
        return {"auto": "auto (自动判断)", "direct": "direct (强制直连)", "proxy": "proxy (强制代理)"}.get(raw, "auto (自动判断)")

    @staticmethod
    def _label_for_cookie(raw: str) -> str:
        return {"none": "none (不使用)", "file": "file (cookies.txt)", "browser": "browser (浏览器)"}.get(raw, "none (不使用)")

    def _proxy_raw(self) -> str:
        v = self.proxy_mode_var.get()
        for raw in ["auto", "direct", "proxy"]:
            if v.startswith(raw):
                return raw
        return "auto"

    def _cookie_raw(self) -> str:
        v = self.cookie_mode_var.get()
        for raw in ["none", "file", "browser"]:
            if v.startswith(raw):
                return raw
        return "none"

    # --------------- 保存 / 取消 ---------------
    def _on_save_click(self):
        self.config.update({
            "proxy_mode": self._proxy_raw(),
            "proxy_url": self.proxy_url_var.get().strip(),
            "cookie_mode": self._cookie_raw(),
            "cookie_path": self.cookie_path_var.get().strip(),
            "cookie_browser": self.cookie_browser_var.get().strip(),
            "auto_open_folder": self.auto_open_var.get(),
            "ffmpeg_path": self.ffmpeg_path_var.get().strip(),
        })
        save_config(self.config)
        self._on_save(self.config)
        self.destroy()

    def _on_cancel(self):
        self.destroy()

    def _center_on_parent(self, parent):
        w = self.winfo_width()
        h = self.winfo_height()
        # 窗口还没渲染时 w/h 会是 1，推迟再算
        if w <= 1 or h <= 1:
            self.after(50, lambda: self._center_on_parent(parent))
            return
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"+{x}+{y}")


# ============================================================
# 下载失败诊断报告对话框
# ============================================================
class ErrorReportDialog(tk.Toplevel):
    """下载失败诊断报告 —— 显示原因、建议、可展开的技术详情。"""

    def __init__(self, parent, report: dict):
        super().__init__(parent)
        self.title("下载失败诊断报告")
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()

        self._report = report
        self._details_visible = False

        apply_theme(self)
        self._build_ui()
        self._center_on_parent(parent)

        # ESC 关闭
        self.bind("<Escape>", lambda _e: self.destroy())

    def _build_ui(self):
        frame = ttk.Frame(self, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)

        # ---- 顶部：错误图标 + 分类标题 ----
        header = ttk.Frame(frame)
        header.pack(fill=tk.X, pady=(0, 12))

        lbl_icon = ttk.Label(header, text="❌", font=("Segoe UI", 20))
        lbl_icon.pack(side=tk.LEFT, padx=(0, 10))

        title_frame = ttk.Frame(header)
        title_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Label(
            title_frame, text="下载失败",
            font=("Microsoft YaHei UI", 12, "bold"),
        ).pack(anchor=tk.W)
        self._category_lbl = ttk.Label(
            title_frame,
            text=self._report.get("category", "未知错误"),
            foreground="#c0392b",
            font=("Microsoft YaHei UI", 10, "bold"),
        )
        self._category_lbl.pack(anchor=tk.W)

        # ---- 原因 ----
        reason_frame = ttk.LabelFrame(frame, text="📋 失败原因", padding=8)
        reason_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(
            reason_frame,
            text=self._report.get("reason", ""),
            wraplength=420,
            justify=tk.LEFT,
        ).pack(anchor=tk.W)

        # ---- 建议 ----
        solution_frame = ttk.LabelFrame(frame, text="💡 解决建议", padding=8)
        solution_frame.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(
            solution_frame,
            text=self._report.get("solution", ""),
            wraplength=420,
            justify=tk.LEFT,
            foreground="#2c3e50",
        ).pack(anchor=tk.W)

        # ---- 技术详情（折叠面板） ----
        self._details_frame = ttk.Frame(frame)
        self._details_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        self._btn_toggle = ttk.Button(
            self._details_frame,
            text="▶ 技术详情（点击展开原始日志）",
            command=self._toggle_details,
        )
        self._btn_toggle.pack(fill=tk.X)

        # 技术详情文本框（初始隐藏）
        self._details_inner = ttk.Frame(self._details_frame)
        # 不 pack，等展开时再显示

        self._detail_text = tk.Text(
            self._details_inner, height=8, state=tk.DISABLED,
            wrap=tk.WORD, font=FONT_MONO,
            background=COLORS["log_bg"], fg=COLORS["text"], relief=tk.FLAT, bd=0,
            highlightbackground=COLORS["border"], highlightcolor=COLORS["border"],
            highlightthickness=1, padx=8, pady=6,
        )
        detail_scroll = ttk.Scrollbar(
            self._details_inner, orient=tk.VERTICAL,
            command=self._detail_text.yview,
        )
        self._detail_text.configure(yscrollcommand=detail_scroll.set)
        self._detail_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        detail_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # 填充原始日志
        lines = self._report.get("all_lines", [])
        self._detail_text.configure(state=tk.NORMAL)
        self._detail_text.insert(tk.END, "\n".join(lines) if lines else "（无输出记录）")
        self._detail_text.configure(state=tk.DISABLED)

        # ---- 底部按钮 ----
        btn_row = ttk.Frame(frame)
        btn_row.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(
            btn_row, text="📋 复制报告",
            command=self._copy_report,
        ).pack(side=tk.LEFT)
        ttk.Button(
            btn_row, text="确定", command=self.destroy,
        ).pack(side=tk.RIGHT)

    def _toggle_details(self):
        """展开 / 收起技术详情。"""
        if self._details_visible:
            self._details_inner.pack_forget()
            self._btn_toggle.configure(text="▶ 技术详情（点击展开原始日志）")
            self._details_visible = False
        else:
            self._details_inner.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
            self._btn_toggle.configure(text="▼ 技术详情（点击收起原始日志）")
            self._details_visible = True

    def _copy_report(self):
        """将结构化报告复制到剪贴板。"""
        r = self._report
        matched = r.get("matched_line", "")
        lines = r.get("all_lines", [])
        text = (
            f"【下载失败诊断报告】\n"
            f"分类：{r.get('category', '')}\n"
            f"原因：{r.get('reason', '')}\n"
            f"建议：{r.get('solution', '')}\n"
        )
        if matched:
            text += f"匹配行：{matched}\n"
        if lines:
            text += f"\n--- 原始日志 ---\n" + "\n".join(lines[-50:])  # 最多 50 行

        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("已复制", "诊断报告已复制到剪贴板。", parent=self)

    def _center_on_parent(self, parent):
        """窗口居中于父窗口。"""
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        if w <= 1 or h <= 1:
            self.after(50, lambda: self._center_on_parent(parent))
            return
        x = parent.winfo_x() + (parent.winfo_width() - w) // 2
        y = parent.winfo_y() + (parent.winfo_height() - h) // 2
        # 确保不超出屏幕
        x = max(0, min(x, self.winfo_screenwidth() - w))
        y = max(0, min(y, self.winfo_screenheight() - h))
        self.geometry(f"+{x}+{y}")


# ============================================================
# GUI 主窗口
# ============================================================
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("视频下载器")
        self.resizable(True, True)
        self.minsize(660, 600)
        self.geometry("720x680")

        # 加载完整配置
        self.config = load_config()
        ensure_dir(self.config["save_dir"])

        self._dl: Downloader | None = None
        self._thread: threading.Thread | None = None
        # 工作线程 → 界面的唯一通道：只入队，主线程统一派发（见 _post / _drain_ui）
        self._ui_queue: queue.Queue = queue.Queue()

        apply_theme(self)
        self._build_ui()
        self._center_window()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # 启动后检查依赖并给出提示
        self.after(80, self._drain_ui)
        self.after(100, self._startup_check)

    def _startup_check(self):
        """启动时检查 yt-dlp 和 ffmpeg 是否可用。"""
        yt_err = check_ytdlp()
        if yt_err:
            self._log(f"[警告] {yt_err}")

        ffmpeg = find_ffmpeg(self.config)
        if ffmpeg:
            self._log(f"[信息] ffmpeg 已找到：{ffmpeg}")
        else:
            ff_warn = check_ffmpeg(self.config)
            if ff_warn:
                self._log(f"[警告] {ff_warn}")

    # --------------- 线程 → 界面：统一队列 ---------------
    def _post(self, fn, *args):
        """把"要在主线程执行的界面动作"放进队列。

        工作线程绝不直接碰 Tk（连 after() 也不能碰：Tcl 不是线程安全的，
        实测从工作线程 after() 会把解释器状态搞坏）。
        """
        try:
            self._ui_queue.put((fn, args))
        except Exception:
            pass

    def _drain_ui(self):
        """主线程定时把队列里的界面动作执行掉。"""
        try:
            while True:
                fn, args = self._ui_queue.get_nowait()
                try:
                    fn(*args)
                except tk.TclError:
                    return          # 窗口没了，停止处理
                except Exception as e:
                    print(f"[警告] 界面更新失败：{e}")
        except queue.Empty:
            pass
        finally:
            try:
                if self.winfo_exists():
                    self.after(80, self._drain_ui)
            except tk.TclError:
                pass                # 窗口已销毁

    # --------------- 日志输出 ---------------
    def _log(self, msg: str):
        """线程安全的日志入口：入队，由主线程写控件。"""
        self._post(self._append_log_line, msg)

    def _append_log_line(self, msg: str):
        """真正操作控件（只在主线程调用），按级别着色（时间戳灰、正文按类型）。"""
        try:
            self.log_text.configure(state=tk.NORMAL)
            ts = datetime.now().strftime("%H:%M:%S")
            if msg.startswith(("[错误", "[失败")):
                tag = "err"
            elif msg.startswith("[警告"):
                tag = "warn"
            elif msg.startswith("[完成"):
                tag = "ok"
            else:
                tag = "info"
            self.log_text.insert(tk.END, f"[{ts}] ", "info")
            self.log_text.insert(tk.END, msg + "\n", tag)
            self.log_text.see(tk.END)
            self.log_text.configure(state=tk.DISABLED)
        except tk.TclError:
            pass   # 窗口已关闭
        except Exception as e:
            print(f"[警告] 写日志失败：{e}")

    # --------------- UI 构建 ---------------
    def _build_ui(self):
        outer = ttk.Frame(self, padding=(20, 16, 20, 18))
        outer.pack(fill=tk.BOTH, expand=True)

        # ---- 顶部标题 ----
        header = tk.Frame(outer, bg=COLORS["bg"])
        header.pack(fill=tk.X, pady=(0, 14))
        accent = tk.Frame(header, bg=COLORS["primary"], width=4, height=40)
        accent.pack(side=tk.LEFT, padx=(0, 10))
        accent.pack_propagate(False)
        title_box = tk.Frame(header, bg=COLORS["bg"])
        title_box.pack(side=tk.LEFT)
        tk.Label(title_box, text="视频下载器", bg=COLORS["bg"], fg=COLORS["text"],
                 font=FONT_TITLE, anchor="w").pack(anchor="w")
        tk.Label(title_box, text="粘贴链接 · 一键下载 · 自动归类", bg=COLORS["bg"],
                 fg=COLORS["muted"], font=FONT_SUB, anchor="w").pack(anchor="w")

        # ---- 视频链接卡片 ----
        link_card = make_card(outer, pady=(0, 10))
        card_title(link_card, "视频链接")
        row1 = ttk.Frame(link_card, style="Card.TFrame")
        row1.pack(fill=tk.X, pady=(8, 0))
        self.url_var = tk.StringVar()
        self.entry_url = ttk.Entry(row1, textvariable=self.url_var)
        self.entry_url.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
        self.entry_url.bind("<Return>", lambda _e: self._start_download())
        self.entry_url.bind("<Control-v>", lambda _e: self.after(10, self._smart_paste))
        self.entry_url.bind("<Button-3>", lambda _e: self.after(10, self._smart_paste))
        self.btn_paste = ttk.Button(
            row1, text="一键粘贴", style="Secondary.TButton",
            command=self._paste_from_clipboard,
        )
        self.btn_paste.pack(side=tk.LEFT, padx=(8, 0))

        # ---- 保存路径卡片 ----
        path_card = make_card(outer, pady=(0, 10))
        card_title(path_card, "保存路径")
        row_path = ttk.Frame(path_card, style="Card.TFrame")
        row_path.pack(fill=tk.X, pady=(8, 0))
        self.path_var = tk.StringVar(value=self.config["save_dir"])
        self.entry_path = ttk.Entry(row_path, textvariable=self.path_var, state="readonly")
        self.entry_path.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
        self.btn_change_path = ttk.Button(
            row_path, text="更改路径", command=self._change_save_dir,
        )
        self.btn_change_path.pack(side=tk.LEFT, padx=(8, 0))

        # ---- 下载选项卡片（格式 / 质量 / 代理） ----
        opt_card = make_card(outer, pady=(0, 10))
        card_title(opt_card, "下载选项")
        row3 = ttk.Frame(opt_card, style="Card.TFrame")
        row3.pack(fill=tk.X, pady=(8, 0))
        ttk.Label(row3, text="格式", style="Field.TLabel").pack(side=tk.LEFT)
        self.format_var = tk.StringVar(value=self.config["default_format"])
        self.cb_format = ttk.Combobox(
            row3, textvariable=self.format_var,
            values=["mp4", "webm", "mp3"], state="readonly", width=8,
        )
        self.cb_format.pack(side=tk.LEFT, padx=(6, 16))
        ttk.Label(row3, text="质量", style="Field.TLabel").pack(side=tk.LEFT)
        self.quality_var = tk.StringVar(value=self.config["default_quality"])
        self.cb_quality = ttk.Combobox(
            row3, textvariable=self.quality_var,
            values=["best", "1080p", "720p", "audio"], state="readonly", width=8,
        )
        self.cb_quality.pack(side=tk.LEFT, padx=(6, 16))
        ttk.Label(row3, text="代理", style="Field.TLabel").pack(side=tk.LEFT)
        self.proxy_mode_var = tk.StringVar(
            value=self._label_for_proxy_mode(self.config["proxy_mode"]),
        )
        self.cb_proxy = ttk.Combobox(
            row3, textvariable=self.proxy_mode_var,
            values=["auto (自动)", "direct (直连)", "proxy (代理)"],
            state="readonly", width=14,
        )
        self.cb_proxy.pack(side=tk.LEFT, padx=(6, 0))

        # 选择变化即时持久化（否则重启丢失）
        self.cb_format.bind("<<ComboboxSelected>>", lambda _e: self._sync_ui_to_config())
        self.cb_quality.bind("<<ComboboxSelected>>", lambda _e: self._sync_ui_to_config())
        self.cb_proxy.bind("<<ComboboxSelected>>", lambda _e: self._sync_ui_to_config())

        # ---- 视频信息卡片 ----
        info_card = make_card(outer, pady=(0, 10))
        card_title(info_card, "视频信息")
        self.lbl_info = ttk.Label(
            info_card, text="等待粘贴链接...", style="Hint.TLabel",
            anchor=tk.W, justify=tk.LEFT,
        )
        self.lbl_info.pack(fill=tk.X, pady=(8, 0))

        # ---- 进度条 + 百分比 ----
        prog_card = make_card(outer, pady=(0, 12))
        self.progress_var = tk.DoubleVar(value=0.0)
        self.progress_bar = ttk.Progressbar(
            prog_card, variable=self.progress_var, maximum=100,
        )
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.lbl_percent = ttk.Label(prog_card, text="0.0%", style="Card.TLabel",
                                     width=7, anchor=tk.E)
        self.lbl_percent.pack(side=tk.RIGHT, padx=(12, 0))

        # ---- 按钮组 ----
        btn_row = ttk.Frame(outer, style="TFrame")
        btn_row.pack(fill=tk.X, pady=(0, 12))

        self.btn_download = ttk.Button(
            btn_row, text="开始下载", style="Accent.TButton", command=self._start_download,
        )
        self.btn_download.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_stop = ttk.Button(
            btn_row, text="停止下载", command=self._stop_download,
            state=tk.DISABLED,
        )
        self.btn_stop.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_open_folder = ttk.Button(
            btn_row, text="打开目录", command=self._open_today_folder,
        )
        self.btn_open_folder.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_settings = ttk.Button(
            btn_row, text="设置", command=self._open_settings,
        )
        self.btn_settings.pack(side=tk.LEFT)

        self.btn_update = ttk.Button(
            btn_row, text="更新核心", style="Secondary.TButton", command=self._update_core,
        )
        self.btn_update.pack(side=tk.RIGHT)

        # ---- 下载日志卡片 ----
        log_card = make_card(outer, pad=(14, 12, 14, 12))
        card_title(log_card, "下载日志")
        log_inner = ttk.Frame(log_card, style="Card.TFrame")
        log_inner.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        self.log_text = tk.Text(
            log_inner, height=7, state=tk.DISABLED, wrap=tk.WORD, font=FONT_MONO,
            bg=COLORS["log_bg"], fg=COLORS["text"], relief=tk.FLAT, bd=0,
            highlightbackground=COLORS["border"], highlightcolor=COLORS["border"],
            highlightthickness=1, padx=8, pady=6,
        )
        log_scrollbar = ttk.Scrollbar(
            log_inner, orient=tk.VERTICAL, command=self.log_text.yview,
        )
        self.log_text.configure(yscrollcommand=log_scrollbar.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(6, 0))

        # 日志级别配色
        self.log_text.tag_configure("info", foreground=COLORS["muted"])
        self.log_text.tag_configure("ok", foreground=COLORS["success"])
        self.log_text.tag_configure("err", foreground=COLORS["error"])
        self.log_text.tag_configure("warn", foreground=COLORS["warn"])

    # --------------- 代理标签 ---------------
    @staticmethod
    def _label_for_proxy_mode(raw: str) -> str:
        return {"auto": "auto (自动)", "direct": "direct (直连)", "proxy": "proxy (代理)"}.get(raw, "auto (自动)")

    @staticmethod
    def _proxy_raw_from_label(label: str) -> str:
        for raw in ["auto", "direct", "proxy"]:
            if label.startswith(raw):
                return raw
        return "auto"

    # --------------- 窗口居中 ---------------
    def _center_window(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"+{x}+{y}")

    # --------------- 一键粘贴 ---------------
    def _extract_url_from_text(self, text: str) -> str | None:
        """从文本中提取第一个 URL；若文本本身就是链接则原样返回。"""
        return extract_url_from_text(text)

    def _paste_from_clipboard(self):
        try:
            text = self.clipboard_get()
        except tk.TclError:
            messagebox.showwarning("剪贴板", "剪贴板为空或无法读取。")
            return
        url = self._extract_url_from_text(text)
        if url:
            self.url_var.set(url)
        else:
            messagebox.showwarning(
                "剪贴板", "剪贴板内容不是有效链接，也未找到 URL。\n已保留原输入框内容。"
            )

    def _smart_paste(self):
        """在输入框内 Ctrl+V / 右键粘贴后自动提取 URL（覆盖粘贴的原始文本）。"""
        try:
            text = self.clipboard_get()
        except tk.TclError:
            return
        url = self._extract_url_from_text(text)
        if url:
            self.url_var.set(url)

    # --------------- 打开今日文件夹 ---------------
    def _open_today_folder(self):
        _, folder_path = get_today_folder(self.config["save_dir"])
        ensure_dir(folder_path)
        os.startfile(folder_path)

    # --------------- 更改保存路径 ---------------
    def _change_save_dir(self):
        new_dir = filedialog.askdirectory(
            title="选择视频保存目录",
            initialdir=self.config["save_dir"],
        )
        if not new_dir:
            return
        self.config["save_dir"] = new_dir
        self.path_var.set(self.config["save_dir"])
        ensure_dir(self.config["save_dir"])
        save_config(self.config)

    # --------------- 打开设置 ---------------
    def _open_settings(self):
        SettingsDialog(self, self.config, self._on_settings_saved)

    def _on_settings_saved(self, new_config: dict):
        self.config = new_config
        self.proxy_mode_var.set(self._label_for_proxy_mode(self.config["proxy_mode"]))
        self.format_var.set(self.config["default_format"])
        self.quality_var.set(self.config["default_quality"])
        self.path_var.set(self.config["save_dir"])
        self._log("[设置] 配置已更新")

    # --------------- 同步 UI 到 config ---------------
    def _sync_ui_to_config(self):
        self.config["proxy_mode"] = self._proxy_raw_from_label(self.proxy_mode_var.get())
        self.config["default_format"] = self.format_var.get()
        self.config["default_quality"] = self.quality_var.get()
        save_config(self.config)

    # --------------- 开始下载 ---------------
    def _start_download(self):
        url = self.url_var.get().strip()
        if not url:
            self._log("[提示] 请先粘贴视频链接。")
            return

        yt_err = check_ytdlp()
        if yt_err:
            self._log(f"[错误] {yt_err}")
            messagebox.showerror("依赖缺失", yt_err)
            return

        self._sync_ui_to_config()

        # 构建输出路径 — 先用日期文件夹 + 临时名，获取标题后更新
        folder_name, target_dir = get_today_folder(self.config["save_dir"])
        ensure_dir(target_dir)
        tmp_ext = output_ext(
            self.config.get("default_format", "mp4"),
            self.config.get("default_quality", "best"),
        )
        output_path = get_next_filepath(target_dir, folder_name, ext=tmp_ext)

        # 查找 FFmpeg
        ffmpeg_path = find_ffmpeg(self.config)
        if ffmpeg_path is None:
            self._log("[警告] 未找到 ffmpeg，部分格式可能无法合并。")

        # 锁定 UI
        self._set_ui_state(tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.progress_var.set(0.0)
        self.lbl_percent.config(text="0.0%")
        self.lbl_info.config(text="正在获取视频信息...", style="Info.TLabel")

        self._dl = Downloader(
            url=url,
            output_path=output_path,
            config=self.config,
            ffmpeg_path=ffmpeg_path,
            info_cb=self._on_info,
            progress_cb=self._on_progress,
            done_cb=self._on_done,
            log_cb=self._log,
            error_cb=self._on_error_report,
        )
        self._thread = threading.Thread(target=self._dl.run, daemon=True)
        self._thread.start()

    # --------------- 视频信息回调 ---------------
    def _on_info(self, info: dict):
        self._post(self._update_info_ui, info)

    def _update_info_ui(self, info: dict):
        title = info.get("title", "?")
        uploader = info.get("uploader", "?")
        duration_s = info.get("duration", 0)
        if duration_s:
            mins, secs = divmod(int(duration_s), 60)
            duration_str = f"{mins}:{secs:02d}"
        else:
            duration_str = "?"
        resolution = info.get("resolution", "?")
        platform = info.get("platform", "?")

        text = (
            f"标题：{title}  |  上传者：{uploader}  |  时长：{duration_str}\n"
            f"分辨率：{resolution}  |  平台：{platform}"
        )
        self.lbl_info.config(text=text, style="Info.TLabel")

        # 文件名已由 Downloader.run() 在下载前同步更新，这里仅记录
        if self._dl and info.get("title"):
            self._log(f"[信息] 文件：{os.path.basename(self._dl.output_path)}")

    # --------------- 进度回调 ---------------
    def _on_progress(self, pct: float):
        self._post(self._update_progress_ui, pct)

    def _update_progress_ui(self, pct: float):
        self.progress_var.set(pct)
        self.lbl_percent.config(text=f"{pct:.1f}%")

    # --------------- 错误报告回调 ---------------
    def _on_error_report(self, report: dict):
        """下载失败时弹出诊断报告对话框。"""
        self._post(lambda: ErrorReportDialog(self, report))

    # --------------- 完成回调 ---------------
    def _on_done(self, ok: bool, msg: str):
        self._post(self._handle_done, ok, msg)

    def _handle_done(self, ok: bool, msg: str):
        self._set_ui_state(tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)

        if ok:
            self._log(f"[完成] {msg}")
            self.url_var.set("")
            self.entry_url.focus_set()
            if self.config.get("auto_open_folder", True):
                _, folder_path = get_today_folder(self.config["save_dir"])
                try:
                    os.startfile(folder_path)
                except Exception:
                    pass
        else:
            self._log(f"[失败] {msg}")

    # --------------- 停止下载 ---------------
    def _stop_download(self):
        if self._dl:
            self._dl.cancel()
        self.btn_stop.config(state=tk.DISABLED)

    # --------------- 更新核心 ---------------
    def _update_core(self):
        self.btn_update.config(state=tk.DISABLED, text="🔄 更新中…")
        t = threading.Thread(
            target=lambda: update_ytdlp(self._on_update_done),
            daemon=True,
        )
        t.start()

    def _on_update_done(self, msg: str):
        self._post(self._handle_update_done, msg)

    def _handle_update_done(self, msg: str):
        self.btn_update.config(state=tk.NORMAL, text="🔄 更新核心")
        self._log(f"[更新核心] {msg}")

    # --------------- UI 状态锁 ---------------
    def _set_ui_state(self, state: str):
        self.entry_url.config(state=state)
        self.btn_paste.config(state=state)
        self.btn_download.config(state=state)
        self.btn_change_path.config(state=state)
        cb_state = "readonly" if str(state) == "normal" else "disabled"
        self.cb_format.config(state=cb_state)
        self.cb_quality.config(state=cb_state)
        self.cb_proxy.config(state=cb_state)
        self.btn_settings.config(state=state)

    # --------------- 关闭窗口 ---------------
    def _on_close(self):
        if self._dl is not None:
            self._dl.cancel()
        self.destroy()


# ============================================================
# 入口
# ============================================================
if __name__ == "__main__":
    try:
        App().mainloop()
    except Exception:
        # 没有顶层兜底的话，双击运行时会"一闪而过"，用户什么都看不到
        import traceback
        tb = traceback.format_exc()
        print(tb)
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("程序启动失败", f"发生错误：\n\n{tb[-1500:]}")
            root.destroy()
        except Exception:
            pass
