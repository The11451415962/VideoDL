#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频下载器 —— Windows 11 Fluent 设计稿 1:1
==============================================
对照用户提供的 Win11 风格稿：
  · 标准窗控（最小化 / 最大化 / 关闭，关闭钮玫瑰红）
  · 左侧栏：顶部品牌 + 首页/下载任务/已完成/关于 + 底部设置
  · 右侧：品牌头 + 链接卡 + 「下载设置」卡 + 虚线预览区 + 按钮行 + 日志卡
后端已内联（原 video_downloader.py 已删除，不依赖该文件）。
"""
import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime


def _msgbox(title: str, text: str, error: bool = False) -> None:
    try:
        import ctypes
        flags = 0x10 if error else 0x40
        ctypes.windll.user32.MessageBoxW(0, text, title, flags)
    except Exception:
        print(f"{title}: {text}")


def _bootstrap_pyside6() -> None:
    try:
        import PySide6  # noqa: F401
        return
    except ImportError:
        pass
    print("首次运行：正在自动安装 PySide6...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "PySide6"])
    except Exception as e:
        _msgbox("依赖缺失", f"安装 PySide6 失败：\n{e}\n请手动 pip install PySide6", error=True)
        raise SystemExit(1)


_bootstrap_pyside6()

from PySide6.QtCore import Qt, QObject, QPoint, QPointF, QRectF, QSize, Signal, QUrl, QTimer
from PySide6.QtGui import (QColor, QFont, QIcon, QPainter, QPen, QPixmap,
                           QPolygonF, QPalette, QTextCursor, QTextCharFormat,
                           QBrush, QFontMetrics)
from PySide6.QtWidgets import (QApplication, QWidget, QDialog, QFrame,
                               QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
                               QLineEdit, QPushButton, QCheckBox,
                               QProgressBar, QTextEdit, QFileDialog,
                               QMessageBox, QGraphicsDropShadowEffect,
                               QScrollArea, QSizePolicy, QStackedWidget,
                               QToolButton, QButtonGroup, QSplitter)
from PySide6.QtCore import QPropertyAnimation, QEasingCurve
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest

# ============================================================
# 内联后端（原 video_downloader.py 的复用部分）
# 该文件已删除，GUI 改为自带后端，core.xxx 调用方式保持不变。
# ============================================================
import shutil
import types
from error_diagnosis import diagnose  # 下载失败诊断模块

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
    # 仅音频：必须 --extract-audio，否则抖音这类只有合并流的站点会把视频
    # 直接存成 .mp3，拖进剪映就「有画面」。bestaudio/best 是为了在
    # 「有纯音频流」时优先用它，没有再退回合并流再抽音轨。
    if fmt == "mp3" or quality == "audio":
        return ["-f", "bestaudio/best", "--extract-audio", "--audio-format", "mp3",
                "--audio-quality", "0"]

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

    另外两处只为了让文件名本身更干净、少给下游 App 添麻烦：
      · URI 敏感字符 `#` / `%` 换成 `_`（社交平台标题里 `#话题` 极常见）
      · **开头只留字母数字**：去掉开头的符号（也避免生成以 `.` 开头的隐藏文件）

    注意：手机上曾出现「App 下载的视频在 ColorOS 相册里点『编辑』报『格式不支持』」，
    一度怀疑是文件名，但**对照实验推翻了**（同一份字节 push 进去就能编辑、App 发布的
    就报错）—— 那个问题在媒体库记录一侧，跟文件名无关。别把这里的清理当成它的修复。
    """
    name = re.sub(r'[\\/:*?"<>|#%]', "_", title or "")
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)
    while name[:1] and not name[0].isalnum():
        name = name[1:]
    name = name.strip().rstrip(". ")
    if not name:
        return "video"
    # 保留名带扩展名同样被 Windows 拒绝（NUL.mp4 也不行），所以取第一段判断。
    # 绕开的方式是在**主干后面**加下划线，不能用 "_" 前缀 —— 前缀会让文件名以
    # 非字母数字开头，正是上面刚要去掉的那种形状。
    if name.split(".")[0].upper() in _WIN_RESERVED:
        stem, dot, ext = name.partition(".")
        name = f"{stem}_{dot}{ext}"
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
    # 抖音要浏览器 UA + Referer，否则接口返回空 JSON（「Fresh cookies needed」）
    if platform == "抖音":
        cmd.extend([
            "--add-header",
            "User-Agent:Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36 Edg/153.0.0.0",
            "--add-header", "Referer:https://www.douyin.com/",
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
    """返回 (vcodec, acodec, duration)；探测失败返回 (None, None, 0)。

    封面图（disposition.attached_pic）不算视频轨 —— 否则带封面的 MP3
    会被当成「有画面」而送去转 H.264，最后变成内容是 MP4、后缀仍是 .mp3
    的怪文件，剪映一拖就识别成视频。
    """
    ffprobe = _ffprobe_path(ffmpeg_path)
    if not ffprobe:
        return None, None, 0.0
    try:
        out = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries",
             "stream=codec_type,codec_name,disposition:format=duration",
             "-of", "json", path],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=60, startupinfo=_startupinfo(),
        )
        data = json.loads((out.stdout or b"{}").decode("utf-8", "replace"))
    except Exception:
        return None, None, 0.0
    vcodec = acodec = None
    for st in data.get("streams", []):
        disposition = st.get("disposition") or {}
        if disposition.get("attached_pic"):
            continue
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


# 音频产物绝不能走「转成 H.264 视频」的兼容兜底，否则会被改成 MP4 内容
AUDIO_EXTS = {".mp3", ".m4a", ".aac", ".opus", ".ogg", ".wav", ".flac", ".wma", ".aiff"}


def ensure_importable(path: str, ffmpeg_path: str | None, duration: float = 0,
                      log_cb=print, progress_cb=None,
                      cancel_check=None) -> tuple[bool, str]:
    """确保文件真的能被手机相册 / 剪映导入。返回 (ok, reason)。"""
    if not os.path.isfile(path):
        return True, ""
    if os.path.splitext(path)[1].lower() in AUDIO_EXTS:
        log_cb("[信息] 音频文件，跳过视频兼容性转码")
        return True, ""
    vcodec, acodec, probed = probe_codecs(path, ffmpeg_path)
    if vcodec is None:
        # 没有真实视频轨（纯音频 / 只有封面）→ 不是「剪映打不开的视频」
        log_cb("[信息] 无视频轨（或仅有封面图），跳过视频兼容性转码")
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
        if platform == "抖音":
            cmd.extend([
                "--add-header",
                "User-Agent:Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36 Edg/153.0.0.0",
                "--add-header", "Referer:https://www.douyin.com/",
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
            if ok:
                self.done_cb(True, "下载完成！")
            else:
                # 文件在，但转码没成：不能再说「完成」，否则用户以为剪映能打开
                self.done_cb(True, "下载完成，但编码不兼容，剪映/相册可能无法打开")
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


core = types.SimpleNamespace(
    Downloader=Downloader,
    check_ffmpeg=check_ffmpeg,
    check_ytdlp=check_ytdlp,
    ensure_dir=ensure_dir,
    extract_url_from_text=extract_url_from_text,
    find_ffmpeg=find_ffmpeg,
    get_next_filepath=get_next_filepath,
    get_today_folder=get_today_folder,
    load_config=load_config,
    output_ext=output_ext,
    save_config=save_config,
    update_ytdlp=update_ytdlp,
)



# ============================================================
# 设计令牌
# ============================================================
PRIMARY = "#3B82F6"
PRIMARY_HOVER = "#2563EB"
PRIMARY_PRESSED = "#1D4ED8"
PRIMARY_SOFT = "#EAF2FF"
LINK = "#2F6FED"

TEXT_TITLE = "#1E293B"
TEXT_BODY = "#475569"
TEXT_MUTED = "#94A3B8"
TEXT_LABEL = "#64748B"

CARD_BG = "#FFFFFF"
CARD_RADIUS = 14
MAIN_BG = "#EEF2F8"
SIDEBAR_BG = "#E8EEF7"
BORDER = "#E4EAF2"
FIELD_BORDER = "#D5DDE8"
DASH_BORDER = "#A8BCD8"
LOG_BG = "#F8FAFC"
LOG_TEXT = "#475569"
CLOSE_RED = "#E85B5B"
CLOSE_RED_HOVER = "#D94A4A"

WINDOW_RADIUS = 12
SIDEBAR_W = 220
TITLEBAR_H = 44

FORMAT_ITEMS = [("MP4", "mp4"), ("WebM", "webm"), ("MP3（仅音频）", "mp3")]
assert "MP4" in [x[0] for x in FORMAT_ITEMS]
QUALITY_ITEMS = [("最佳画质", "best"), ("1080P", "1080p"),
                 ("720P", "720p"), ("仅音频", "audio")]
PROXY_ITEMS = [("自动", "auto"), ("直连", "direct"), ("强制代理", "proxy")]

SPEED_RE = re.compile(r"at\s+([0-9.]+[KMG]?i?B/s)")
ETA_RE = re.compile(r"ETA\s+([0-9:]+)")


# ============================================================
# 图标
# ============================================================
def _painter_icon(size, draw_fn) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    draw_fn(p, size)
    p.end()
    return QIcon(pm)


def _icon_app_box(size=56) -> QIcon:
    def draw(p, s):
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(PRIMARY))
        r = int(s * 0.26)
        p.drawRoundedRect(1, 1, s - 2, s - 2, r, r)
        pen = QPen(QColor("#FFFFFF"), max(2.0, s * 0.08))
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        cx, cy = s / 2, s * 0.42
        p.drawLine(QPointF(cx, cy - s * 0.15), QPointF(cx, cy + s * 0.16))
        p.drawLine(QPointF(cx - s * 0.14, cy + s * 0.02), QPointF(cx, cy + s * 0.16))
        p.drawLine(QPointF(cx + s * 0.14, cy + s * 0.02), QPointF(cx, cy + s * 0.16))
        p.drawLine(QPointF(cx - s * 0.16, s * 0.74), QPointF(cx + s * 0.16, s * 0.74))
    return _painter_icon(size, draw)


def _icon_glyph(kind: str, color: str = TEXT_LABEL, size: int = 20) -> QIcon:
    def draw(p, s):
        pen = QPen(QColor(color), 1.6)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        u = s / 20.0
        if kind == "home":
            p.drawPolygon(QPolygonF([
                QPointF(4.5 * u, 10 * u), QPointF(10 * u, 5 * u),
                QPointF(15.5 * u, 10 * u),
            ]))
            p.drawRoundedRect(QRectF(6.5 * u, 10 * u, 7 * u, 6 * u), 1, 1)
        elif kind == "down":
            p.drawLine(QPointF(10 * u, 4.5 * u), QPointF(10 * u, 13 * u))
            p.drawLine(QPointF(6.5 * u, 9.5 * u), QPointF(10 * u, 13 * u))
            p.drawLine(QPointF(13.5 * u, 9.5 * u), QPointF(10 * u, 13 * u))
            p.drawLine(QPointF(5.5 * u, 15.5 * u), QPointF(14.5 * u, 15.5 * u))
        elif kind == "check":
            p.drawEllipse(QPointF(10 * u, 10 * u), 6.3 * u, 6.3 * u)
            p.drawLine(QPointF(7.2 * u, 10 * u), QPointF(9.2 * u, 12 * u))
            p.drawLine(QPointF(9.2 * u, 12 * u), QPointF(13 * u, 8.2 * u))
        elif kind == "info":
            p.drawEllipse(QPointF(10 * u, 10 * u), 6.3 * u, 6.3 * u)
            p.drawLine(QPointF(10 * u, 9 * u), QPointF(10 * u, 14 * u))
            p.drawPoint(QPointF(10 * u, 6.8 * u))
        elif kind == "gear":
            import math
            p.drawEllipse(QPointF(10 * u, 10 * u), 3.0 * u, 3.0 * u)
            for a in range(8):
                ang = a * (math.pi / 4)
                p.drawLine(
                    QPointF(10 * u + 5.0 * u * math.cos(ang), 10 * u + 5.0 * u * math.sin(ang)),
                    QPointF(10 * u + 6.8 * u * math.cos(ang), 10 * u + 6.8 * u * math.sin(ang)),
                )
        elif kind == "refresh":
            p.drawArc(QRectF(5 * u, 5 * u, 10 * u, 10 * u), 40 * 16, 280 * 16)
            p.drawLine(QPointF(13.5 * u, 6 * u), QPointF(13.8 * u, 8.5 * u))
            p.drawLine(QPointF(13.8 * u, 6 * u), QPointF(11.2 * u, 6.3 * u))
        elif kind == "link":
            p.drawRoundedRect(QRectF(3.5 * u, 7.5 * u, 8 * u, 5 * u), 2.5 * u, 2.5 * u)
            p.drawRoundedRect(QRectF(8.5 * u, 7.5 * u, 8 * u, 5 * u), 2.5 * u, 2.5 * u)
        elif kind == "clipboard":
            p.drawRoundedRect(QRectF(5 * u, 5 * u, 10 * u, 12 * u), 2, 2)
            p.drawRoundedRect(QRectF(7.5 * u, 3.5 * u, 5 * u, 3 * u), 1, 1)
        elif kind == "folder":
            p.drawRoundedRect(QRectF(3.5 * u, 7.5 * u, 13 * u, 8 * u), 1.5, 1.5)
            p.drawRoundedRect(QRectF(3.5 * u, 5.5 * u, 6 * u, 3 * u), 1, 1)
        elif kind == "format":
            p.drawRoundedRect(QRectF(3.5 * u, 6 * u, 13 * u, 8.5 * u), 1.5, 1.5)
        elif kind == "quality":
            p.drawRoundedRect(QRectF(3.5 * u, 5 * u, 13 * u, 10 * u), 1.5, 1.5)
            p.drawEllipse(QPointF(7.5 * u, 8.5 * u), 1.2 * u, 1.2 * u)
            p.drawPolyline(QPolygonF([
                QPointF(4.5 * u, 13 * u), QPointF(9 * u, 9 * u),
                QPointF(12 * u, 11.5 * u), QPointF(16 * u, 8 * u),
            ]))
        elif kind == "globe":
            p.drawEllipse(QPointF(10 * u, 10 * u), 6.2 * u, 6.2 * u)
            p.drawLine(QPointF(3.8 * u, 10 * u), QPointF(16.2 * u, 10 * u))
            p.drawArc(QRectF(6.5 * u, 3.8 * u, 7 * u, 12.4 * u), 0, 360 * 16)
        elif kind == "play":
            p.setBrush(QColor(PRIMARY))
            p.setPen(QPen(QColor(PRIMARY), 1.2))
            p.drawPolygon(QPolygonF([
                QPointF(8 * u, 6.5 * u), QPointF(8 * u, 13.5 * u),
                QPointF(14 * u, 10 * u),
            ]))
        elif kind == "pause":
            p.setBrush(QColor(TEXT_LABEL))
            p.setPen(Qt.NoPen)
            p.drawRoundedRect(QRectF(7 * u, 6.5 * u, 2.2 * u, 7 * u), 1, 1)
            p.drawRoundedRect(QRectF(11 * u, 6.5 * u, 2.2 * u, 7 * u), 1, 1)
        elif kind == "doc":
            p.drawRoundedRect(QRectF(5 * u, 3.5 * u, 10 * u, 13 * u), 1.5, 1.5)
            p.drawLine(QPointF(7.5 * u, 8 * u), QPointF(12.5 * u, 8 * u))
            p.drawLine(QPointF(7.5 * u, 11 * u), QPointF(12.5 * u, 11 * u))
        elif kind == "sparkle":
            p.drawPolygon(QPolygonF([
                QPointF(10 * u, 3.5 * u), QPointF(11.2 * u, 8 * u),
                QPointF(15.5 * u, 9.2 * u), QPointF(11.2 * u, 10.4 * u),
                QPointF(10 * u, 15 * u), QPointF(8.8 * u, 10.4 * u),
                QPointF(4.5 * u, 9.2 * u), QPointF(8.8 * u, 8 * u),
            ]))
        elif kind == "chevron":
            p.drawLine(QPointF(8 * u, 6.5 * u), QPointF(12.5 * u, 10 * u))
            p.drawLine(QPointF(12.5 * u, 10 * u), QPointF(8 * u, 13.5 * u))
        elif kind == "chevron_up":
            p.drawLine(QPointF(6.5 * u, 12 * u), QPointF(10 * u, 8 * u))
            p.drawLine(QPointF(10 * u, 8 * u), QPointF(13.5 * u, 12 * u))
    return _painter_icon(size, draw)


def _add_shadow(widget: QWidget, blur=20, alpha=16, y=3):
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setOffset(0, y)
    eff.setColor(QColor(15, 23, 42, alpha))
    widget.setGraphicsEffect(eff)


def _make_card() -> QFrame:
    card = QFrame()
    card.setObjectName("card")
    _add_shadow(card)
    return card


def _make_button(text: str, obj: str = "secondary", height: int = 40,
                 width: int = 0, on_click=None, icon: QIcon | None = None) -> QPushButton:
    btn = QPushButton(text)
    btn.setObjectName(obj)
    btn.setFixedHeight(height)
    if width:
        btn.setFixedWidth(width)
    btn.setCursor(Qt.PointingHandCursor)
    if icon is not None:
        btn.setIcon(icon)
    if on_click is not None:
        btn.clicked.connect(on_click)
    return btn


class _DropList(QWidget):
    """弹层列表：自绘选项。选项少时不滚动；多时用自定义细滚动条（无系统箭头）。"""

    ITEM_H = 36
    PAD = 8

    def __init__(self, popup):
        super().__init__(popup)
        self._popup = popup
        self._hover = -1
        self._offset = 0  # 自定义滚动偏移
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAttribute(Qt.WA_OpaquePaintEvent, False)

    def _items(self):
        return self._popup._select._items

    def _visible_rows(self):
        return min(len(self._items()), 8)

    def _need_scroll(self):
        return len(self._items()) > 8

    def sizeHint(self):
        return QSize(160, self._visible_rows() * self.ITEM_H + self.PAD * 2)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # 背景由弹层画圆角，这里只画选项，避免直角白底露出四个角
        items = self._items()
        cur = self._popup._select.currentIndex()
        w = self.width() - (8 if self._need_scroll() else 0)
        for i, (label, _val) in enumerate(items):
            y = self.PAD + i * self.ITEM_H - self._offset
            if y + self.ITEM_H < 0 or y > self.height():
                continue
            rect = QRectF(6, y + 1, w - 12, self.ITEM_H - 2)
            if i == cur:
                p.setBrush(QColor(PRIMARY_SOFT))
                p.setPen(Qt.NoPen)
                p.drawRoundedRect(rect, 8, 8)
            elif i == self._hover:
                p.setBrush(QColor("#F1F5F9"))
                p.setPen(Qt.NoPen)
                p.drawRoundedRect(rect, 8, 8)
            color = QColor(PRIMARY_HOVER) if i == cur else QColor(TEXT_TITLE)
            font = self.font()
            font.setPixelSize(13)
            font.setWeight(QFont.Weight.DemiBold if i == cur else QFont.Weight.Normal)
            p.setFont(font)
            p.setPen(QPen(color))
            p.drawText(rect.adjusted(10, 0, -10, 0), Qt.AlignVCenter | Qt.AlignLeft, label)

        # 自定义细滚动条（无上下箭头，不是系统原生样式）
        if self._need_scroll():
            total_h = len(items) * self.ITEM_H
            view_h = self.height() - self.PAD * 2
            if total_h > view_h:
                ratio = view_h / total_h
                bar_h = max(28, int(view_h * ratio))
                max_off = total_h - view_h
                bar_y = self.PAD + int((view_h - bar_h) * (self._offset / max_off if max_off else 0))
                p.setPen(Qt.NoPen)
                p.setBrush(QColor("#E2E8F0"))
                p.drawRoundedRect(QRectF(self.width() - 6, self.PAD, 3, view_h), 1.5, 1.5)
                p.setBrush(QColor("#94A3B8"))
                p.drawRoundedRect(QRectF(self.width() - 6, bar_y, 3, bar_h), 1.5, 1.5)
        p.end()

    def wheelEvent(self, ev):
        if not self._need_scroll():
            return
        total_h = len(self._items()) * self.ITEM_H
        view_h = self.height() - self.PAD * 2
        max_off = max(0, total_h - view_h)
        self._offset = max(0, min(max_off, self._offset - int(ev.angleDelta().y() / 2)))
        self.update()

    def _index_at(self, pos) -> int:
        y = pos.y() - self.PAD + self._offset
        i = int(y // self.ITEM_H)
        return i if 0 <= i < len(self._items()) else -1

    def mouseMoveEvent(self, ev):
        self._hover = self._index_at(ev.position().toPoint())
        self.update()

    def mouseReleaseEvent(self, ev):
        i = self._index_at(ev.position().toPoint())
        if i >= 0:
            self._popup._select.setCurrentIndex(i)
        self._popup.closeAnimated()

    def keyPressEvent(self, ev):
        sel = self._popup._select
        k = ev.key()
        if k == Qt.Key_Escape:
            self._popup.closeAnimated()
        elif k in (Qt.Key_Return, Qt.Key_Enter):
            self._popup.closeAnimated()
        elif k == Qt.Key_Down:
            sel.setCurrentIndex(min(sel.currentIndex() + 1, len(sel._items) - 1))
            self.update()
        elif k == Qt.Key_Up:
            sel.setCurrentIndex(max(sel.currentIndex() - 1, 0))
            self.update()
        else:
            super().keyPressEvent(ev)


class DropdownPopup(QFrame):
    """浮层下拉：不参与页面布局，Qt.Popup 保证点外部关闭。"""

    ITEM_H = 36
    PAD = 8

    def __init__(self, select: "CustomSelect"):
        super().__init__(None, Qt.Popup | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self._select = select
        self.setObjectName("dropPopup")
        self.setFocusPolicy(Qt.StrongFocus)
        self._anim_pos = None
        self._anim_op = None
        # 透明画布 + 自绘圆角，去掉 QGraphicsDropShadowEffect（会在无边框窗四角露出直角）
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)
        self.setStyleSheet("QFrame#dropPopup { background: transparent; border: none; }")

        n = max(1, len(select._items))
        rows = min(n, 8)  # 超过 8 条才内部滚动
        w = max(select.width(), 160)  # 与选择框同宽
        h = rows * self.ITEM_H + self.PAD * 2
        self.setFixedSize(w, h)

        self._list = _DropList(self)
        self._list.setGeometry(0, 0, w, h)
        self._list.setAttribute(Qt.WA_TransparentForMouseEvents, False)

    def paintEvent(self, ev):
        # 自绘：轻阴影 + 圆角白底 + 细边框（四角平滑，无直角残影）
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(0, 0, self.width(), self.height())
        # 轻微外阴影（用半透明圆角叠一层，比 QGraphicsDropShadowEffect 干净）
        for i, a in enumerate((10, 6, 3)):
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(15, 23, 42, a))
            p.drawRoundedRect(r.adjusted(-1, 1, 1, 3 + i), 12, 12)
        p.setBrush(QColor("#FFFFFF"))
        p.setPen(QPen(QColor(BORDER), 1))
        p.drawRoundedRect(r.adjusted(0.5, 0.5, -0.5, -0.5), 12, 12)
        p.end()

    def open_at(self, global_pos: QPoint):
        """先定位到选择框下方，再播放打开动画。"""
        self.move(global_pos)
        final_pos = QPoint(global_pos)
        start_pos = QPoint(global_pos.x(), global_pos.y() - 4)
        self.move(start_pos)
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self.activateWindow()
        self._list.setFocus()

        self._anim_pos = QPropertyAnimation(self, b"pos", self)
        self._anim_pos.setDuration(120)
        self._anim_pos.setStartValue(start_pos)
        self._anim_pos.setEndValue(final_pos)
        self._anim_pos.setEasingCurve(QEasingCurve.OutCubic)

        self._anim_op = QPropertyAnimation(self, b"windowOpacity", self)
        self._anim_op.setDuration(120)
        self._anim_op.setStartValue(0.0)
        self._anim_op.setEndValue(1.0)
        self._anim_op.setEasingCurve(QEasingCurve.OutCubic)

        self._anim_pos.start()
        self._anim_op.start()

    def closeAnimated(self):
        if self._anim_pos is not None:
            self._anim_pos.stop()
        if self._anim_op is not None:
            self._anim_op.stop()
        end_pos = QPoint(self.x(), self.y() - 3)
        self._anim_pos = QPropertyAnimation(self, b"pos", self)
        self._anim_pos.setDuration(100)
        self._anim_pos.setStartValue(self.pos())
        self._anim_pos.setEndValue(end_pos)
        self._anim_pos.setEasingCurve(QEasingCurve.InCubic)

        self._anim_op = QPropertyAnimation(self, b"windowOpacity", self)
        self._anim_op.setDuration(100)
        self._anim_op.setStartValue(max(0.0, float(self.windowOpacity())))
        self._anim_op.setEndValue(0.0)
        self._anim_op.setEasingCurve(QEasingCurve.InCubic)
        self._anim_op.finished.connect(self._after_close)
        self._anim_pos.start()
        self._anim_op.start()

    def _after_close(self):
        self._select._popup = None
        self.close()
        self.deleteLater()

    def closeEvent(self, ev):
        # 点击外部：Qt.Popup 直接 close，这里清引用
        self._select._popup = None
        super().closeEvent(ev)

    def keyPressEvent(self, ev):
        sel = self._select
        k = ev.key()
        if k == Qt.Key_Escape:
            self.closeAnimated()
        elif k in (Qt.Key_Return, Qt.Key_Enter):
            self.closeAnimated()
        elif k == Qt.Key_Down:
            sel.setCurrentIndex(min(sel.currentIndex() + 1, len(sel._items) - 1))
            self._list.update()
        elif k == Qt.Key_Up:
            sel.setCurrentIndex(max(sel.currentIndex() - 1, 0))
            self._list.update()
        else:
            super().keyPressEvent(ev)


class CustomSelect(QWidget):
    """替代 QComboBox：点击后在应用内弹出自绘菜单，不走系统原生下拉。"""

    currentIndexChanged = Signal(int)

    def __init__(self, items=None, current=None, parent=None):
        super().__init__(parent)
        self.setObjectName("customSelect")
        self._items: list[tuple[str, object]] = []
        self._index = 0
        self._popup = None
        self._enabled = True
        self.setFixedHeight(42)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumWidth(120)
        if items:
            for label, value in items:
                self.addItem(label, value)
            idx = self.findData(current)
            self.setCurrentIndex(idx if idx >= 0 else 0)

    # ---- QComboBox 兼容 API ----
    def addItem(self, label, value=None):
        self._items.append((label, value))

    def findData(self, value):
        for i, (_l, v) in enumerate(self._items):
            if v == value:
                return i
        return -1

    def currentIndex(self):
        return self._index

    def currentData(self):
        if 0 <= self._index < len(self._items):
            return self._items[self._index][1]
        return None

    def currentText(self):
        if 0 <= self._index < len(self._items):
            return self._items[self._index][0]
        return ""

    def setCurrentIndex(self, idx):
        if not self._items:
            return
        idx = max(0, min(int(idx), len(self._items) - 1))
        if idx == self._index:
            self.update()
            return
        self._index = idx
        self.update()
        self.currentIndexChanged.emit(idx)

    def blockSignals(self, b):
        return super().blockSignals(b)

    def setEnabled(self, enabled: bool):
        self._enabled = enabled
        super().setEnabled(enabled)
        self.setCursor(Qt.PointingHandCursor if enabled else Qt.ArrowCursor)
        self.update()

    def items(self):
        return list(self._items)

    # ---- 交互 ----
    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(1, 1, -1, -1)
        enabled = self.isEnabled()
        bg = QColor("#F5F7FB") if not enabled else QColor("#FFFFFF")
        border = QColor(BORDER) if not enabled else (
            QColor(PRIMARY) if self.hasFocus() or self._popup else QColor(FIELD_BORDER))
        if enabled and self.underMouse() and not self._popup:
            border = QColor("#B8C4D4")
        p.setBrush(bg)
        p.setPen(QPen(border, 1.2 if border == QColor(PRIMARY) else 1.0))
        p.drawRoundedRect(r, 10, 10)

        text = self.currentText()
        color = QColor(TEXT_MUTED) if not enabled else QColor(TEXT_TITLE)
        font = self.font()
        font.setPixelSize(13)
        p.setFont(font)
        p.setPen(QPen(color))
        p.drawText(r.adjusted(12, 0, -32, 0), Qt.AlignVCenter | Qt.AlignLeft, text)

        # 箭头
        pen = QPen(QColor(TEXT_LABEL if enabled else TEXT_MUTED), 1.5)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        cx, cy = self.width() - 18, self.height() / 2
        p.drawLine(QPointF(cx - 4, cy - 2), QPointF(cx, cy + 2.5))
        p.drawLine(QPointF(cx, cy + 2.5), QPointF(cx + 4, cy - 2))
        p.end()

    def mousePressEvent(self, ev):
        if not self.isEnabled():
            return
        self._toggle_popup()

    def keyPressEvent(self, ev):
        if not self.isEnabled():
            return
        k = ev.key()
        if k in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter, Qt.Key_Down):
            self._toggle_popup()
        elif k == Qt.Key_Up:
            self.setCurrentIndex(max(0, self.currentIndex() - 1))
        else:
            super().keyPressEvent(ev)

    def _toggle_popup(self):
        if self._popup is not None:
            self._popup.closeAnimated()
            return
        popup = DropdownPopup(self)  # 构造时按本控件宽度定宽
        gap = 6  # 与选择框 4~6px 间距
        pos = self.mapToGlobal(QPoint(0, self.height() + gap))
        screen = self.screen()
        if screen is not None:
            sg = screen.availableGeometry()
            if pos.y() + popup.height() > sg.bottom() - 8:
                pos = self.mapToGlobal(QPoint(0, -popup.height() - gap))
            pos.setX(max(sg.left() + 4, min(pos.x(), sg.right() - popup.width() - 4)))
        popup.open_at(pos)  # 定位后再播动画，避免飞到左上角
        self._popup = popup
        self.update()

    def hidePopupIfAny(self):
        if self._popup is not None:
            self._popup.closeAnimated()


def _make_combo(items, current):
    """创建自定义下拉（API 与原 QComboBox 用法兼容）。"""
    cb = CustomSelect()
    for label, value in items:
        cb.addItem(label, value)
    idx = cb.findData(current)
    cb.setCurrentIndex(idx if idx >= 0 else 0)
    cb.setFixedHeight(42)
    return cb


def _icon_label_row(icon: QIcon, text: str):
    row = QHBoxLayout()
    row.setSpacing(6)
    row.setContentsMargins(0, 0, 0, 0)
    lab = QLabel()
    lab.setPixmap(icon.pixmap(16, 16))
    lab.setScaledContents(True)
    lab.setFixedSize(16, 16)
    row.addWidget(lab, 0, Qt.AlignVCenter)
    t = QLabel(text)
    t.setObjectName("fieldLabel")
    row.addWidget(t, 0, Qt.AlignVCenter)
    row.addStretch(1)
    wrap = QWidget()
    wrap.setLayout(row)
    return wrap


def _make_field(label_text: str, widget, icon_kind: str | None = None):
    box = QVBoxLayout()
    box.setSpacing(8)
    box.setContentsMargins(0, 0, 0, 0)
    if icon_kind:
        box.addWidget(_icon_label_row(_icon_glyph(icon_kind, TEXT_LABEL, 18), label_text))
    else:
        lab = QLabel(label_text)
        lab.setObjectName("fieldLabel")
        box.addWidget(lab)
    if isinstance(widget, QWidget):
        box.addWidget(widget)
    else:
        holder = QWidget()
        holder.setLayout(widget)
        box.addWidget(holder)
    wrap = QWidget()
    wrap.setObjectName("fieldWrap")
    wrap.setLayout(box)
    return wrap


class _LogView(QTextEdit):
    def sizeHint(self) -> QSize:
        return QSize(super().sizeHint().width(), 100)


class DownloadSignals(QObject):
    info = Signal(dict)
    progress = Signal(float)
    done = Signal(bool, str)
    log = Signal(str)
    error = Signal(dict)
    core_update = Signal(str)


# ============================================================
# 设置对话框
# ============================================================
class SettingsDialog(QDialog):
    COOKIE_BROWSERS = ["chrome", "firefox", "edge", "opera", "brave", "safari"]
    PROXY_MODES = [("自动（YouTube 走代理）", "auto"), ("直连", "direct"), ("强制代理", "proxy")]
    COOKIE_MODES = [("不使用", "none"), ("cookies.txt 文件", "file"), ("从浏览器读取", "browser")]

    def __init__(self, parent, config: dict, on_save):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setObjectName("settingsDialog")
        self.setModal(True)
        self.setMinimumWidth(560)
        self._on_save = on_save
        self._cfg = dict(config)
        self._build_ui()
        for lbl in (self.lbl_proxy_hint, self.lbl_ffmpeg_state):
            lbl.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.resize(640, self.sizeHint().height())
        self.setStyleSheet(f"QDialog#settingsDialog {{ background: {MAIN_BG}; }}")

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)
        root.addWidget(self._build_proxy_card())
        root.addWidget(self._build_cookie_card())
        root.addWidget(self._build_other_card())
        root.addLayout(self._build_button_row())

    @staticmethod
    def _card(title: str):
        card = _make_card()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 14)
        lay.setSpacing(10)
        head = QLabel(title)
        head.setObjectName("cardTitle")
        lay.addWidget(head)
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        lay.addLayout(grid)
        return card, grid

    def _build_proxy_card(self):
        card, grid = self._card("代理设置")
        self.cb_proxy_mode = _make_combo(self.PROXY_MODES, self._cfg.get("proxy_mode", "auto"))
        grid.addWidget(_make_field("模式", self.cb_proxy_mode), 0, 0)
        self.ed_proxy_url = QLineEdit(self._cfg.get("proxy_url", "") or "")
        self.ed_proxy_url.setFixedHeight(42)
        self.ed_proxy_url.setPlaceholderText("http://127.0.0.1:7897")
        grid.addWidget(_make_field("地址", self.ed_proxy_url), 0, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        self.lbl_proxy_hint = QLabel()
        self.lbl_proxy_hint.setObjectName("fieldLabel")
        self.lbl_proxy_hint.setWordWrap(True)
        grid.addWidget(self.lbl_proxy_hint, 1, 0, 1, 2)
        self.cb_proxy_mode.currentIndexChanged.connect(self._on_proxy_mode_change)
        self._on_proxy_mode_change()
        return card

    def _build_cookie_card(self):
        card, grid = self._card("Cookie 设置")
        self.cb_cookie_mode = _make_combo(self.COOKIE_MODES, self._cfg.get("cookie_mode", "none"))
        grid.addWidget(_make_field("模式", self.cb_cookie_mode), 0, 0)
        self.cb_browser = _make_combo([(b, b) for b in self.COOKIE_BROWSERS],
                                      self._cfg.get("cookie_browser", "chrome"))
        self.wrap_browser = _make_field("浏览器", self.cb_browser)
        grid.addWidget(self.wrap_browser, 0, 1)
        self.ed_cookie_path = QLineEdit(self._cfg.get("cookie_path", "") or "")
        self.ed_cookie_path.setFixedHeight(42)
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self.ed_cookie_path, 1)
        row.addWidget(_make_button("浏览", "secondary", 42, 72, self._browse_cookie))
        holder = QWidget()
        holder.setLayout(row)
        self.wrap_cookie_path = _make_field("文件", holder)
        grid.addWidget(self.wrap_cookie_path, 1, 0, 1, 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        self.cb_cookie_mode.currentIndexChanged.connect(self._on_cookie_mode_change)
        self._on_cookie_mode_change()
        return card

    def _build_other_card(self):
        card, grid = self._card("FFmpeg / 其他")
        self.ed_ffmpeg = QLineEdit(self._cfg.get("ffmpeg_path", "") or "")
        self.ed_ffmpeg.setFixedHeight(42)
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self.ed_ffmpeg, 1)
        row.addWidget(_make_button("浏览", "secondary", 42, 72, self._browse_ffmpeg))
        holder = QWidget()
        holder.setLayout(row)
        grid.addWidget(_make_field("FFmpeg 路径", holder, "folder"), 0, 0, 1, 2)
        self.lbl_ffmpeg_state = QLabel()
        self.lbl_ffmpeg_state.setObjectName("fieldLabel")
        self.lbl_ffmpeg_state.setWordWrap(True)
        grid.addWidget(self.lbl_ffmpeg_state, 1, 0, 1, 2)
        self.cb_auto_open = QCheckBox("下载完成后自动打开文件夹")
        self.cb_auto_open.setChecked(bool(self._cfg.get("auto_open_folder", True)))
        grid.addWidget(self.cb_auto_open, 2, 0, 1, 2)
        self.ed_ffmpeg.textChanged.connect(self._refresh_ffmpeg_state)
        self._refresh_ffmpeg_state()
        return card

    def _build_button_row(self):
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(_make_button("恢复默认", "ghost", 36, on_click=self._reset_defaults))
        row.addWidget(_make_button("取消", "secondary", 36, 88, self.reject))
        row.addWidget(_make_button("保存", "primary", 36, 88, self._on_accept))
        return row

    def _on_proxy_mode_change(self, *_):
        self.ed_proxy_url.setEnabled(self.cb_proxy_mode.currentData() != "direct")

    def _on_cookie_mode_change(self, *_):
        mode = self.cb_cookie_mode.currentData()
        self.wrap_browser.setVisible(mode == "browser")
        self.wrap_cookie_path.setVisible(mode == "file")

    def _refresh_ffmpeg_state(self, *_):
        path = self.ed_ffmpeg.text().strip()
        if path and os.path.isfile(path):
            self.lbl_ffmpeg_state.setText(f"已找到：{path}")
        else:
            found = core.find_ffmpeg({**self._cfg, "ffmpeg_path": path})
            self.lbl_ffmpeg_state.setText(f"自动查找：{found or '未找到'}")

    def _browse_cookie(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 cookies.txt", "", "Text (*.txt)")
        if path:
            self.ed_cookie_path.setText(path)

    def _browse_ffmpeg(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择 ffmpeg", "", "Executable (*.exe)")
        if path:
            self.ed_ffmpeg.setText(path)

    def _reset_defaults(self):
        self.cb_proxy_mode.setCurrentIndex(0)
        self.ed_proxy_url.setText("http://127.0.0.1:7897")
        self.cb_cookie_mode.setCurrentIndex(0)
        self.ed_cookie_path.clear()
        self.ed_ffmpeg.clear()
        self.cb_auto_open.setChecked(True)

    def _collect(self) -> dict:
        cfg = dict(self._cfg)
        cfg["proxy_mode"] = self.cb_proxy_mode.currentData()
        cfg["proxy_url"] = self.ed_proxy_url.text().strip()
        cfg["cookie_mode"] = self.cb_cookie_mode.currentData()
        cfg["cookie_path"] = self.ed_cookie_path.text().strip()
        cfg["cookie_browser"] = self.cb_browser.currentData()
        cfg["ffmpeg_path"] = self.ed_ffmpeg.text().strip()
        cfg["auto_open_folder"] = self.cb_auto_open.isChecked()
        return cfg

    def _validate(self, cfg: dict) -> str | None:
        if cfg["proxy_mode"] != "direct" and not cfg["proxy_url"]:
            return "代理模式需要填写代理地址"
        if cfg["cookie_mode"] == "file" and cfg["cookie_path"] and not os.path.isfile(cfg["cookie_path"]):
            return "cookies.txt 路径不存在"
        if cfg["ffmpeg_path"] and not os.path.isfile(cfg["ffmpeg_path"]):
            return "FFmpeg 路径不存在"
        return None

    def _on_accept(self):
        cfg = self._collect()
        err = self._validate(cfg)
        if err:
            QMessageBox.warning(self, "设置", err)
            return
        try:
            core.save_config(cfg)
        except OSError as e:
            QMessageBox.critical(self, "设置", f"写入 config.json 失败：\n{e}")
            return
        self._on_save(cfg)
        self.accept()


class NavButton(QPushButton):
    def __init__(self, text: str, icon_kind: str, key: str):
        super().__init__(text)
        self.key = key
        self.setCheckable(True)
        self.setObjectName("navBtn")
        self.setFixedHeight(44)
        self.setCursor(Qt.PointingHandCursor)
        self.setIcon(_icon_glyph(icon_kind, TEXT_LABEL, 20))


class CapButton(QToolButton):
    """Win11 标题栏按钮：最小化 / 最大化 / 关闭。"""

    def __init__(self, kind: str):
        super().__init__()
        self.kind = kind
        self.setFixedSize(48, TITLEBAR_H)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("QToolButton { border: none; background: transparent; }")

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        hover = self.underMouse()
        if self.kind == "close" and hover:
            p.fillRect(self.rect(), QColor(CLOSE_RED))
        elif hover:
            p.fillRect(self.rect(), QColor(15, 23, 42, 14))
        color = QColor("#FFFFFF") if (self.kind == "close" and hover) else QColor(TEXT_BODY)
        pen = QPen(color, 1.3)
        pen.setCapStyle(Qt.FlatCap)
        p.setPen(pen)
        cx, cy = self.width() / 2, self.height() / 2
        if self.kind == "min":
            p.drawLine(QPointF(cx - 6, cy), QPointF(cx + 6, cy))
        elif self.kind == "max":
            p.drawRect(QRectF(cx - 5.5, cy - 5.5, 11, 11))
        else:
            p.drawLine(QPointF(cx - 5, cy - 5), QPointF(cx + 5, cy + 5))
            p.drawLine(QPointF(cx + 5, cy - 5), QPointF(cx - 5, cy + 5))
        p.end()


class HistoryCard(QFrame):
    """已完成页：封面 + 标题 + 时长/耗时/时间 + 打开/删除。"""

    def __init__(self, item: dict, on_delete, on_open):
        super().__init__()
        self.setObjectName("histCard")
        self.item = item
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(14)

        thumb = QLabel()
        thumb.setObjectName("histThumb")
        thumb.setFixedSize(128, 72)
        thumb.setScaledContents(True)
        pm = QPixmap(item.get("thumb_path") or "")
        if pm.isNull():
            # 占位：淡灰圆角
            pm = QPixmap(128, 72)
            pm.fill(QColor("#E8EEF5"))
            p = QPainter(pm)
            p.setRenderHint(QPainter.Antialiasing)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#B6C4D8"))
            p.drawPolygon(QPolygonF([
                QPointF(52, 24), QPointF(52, 48), QPointF(76, 36),
            ]))
            p.end()
        thumb.setPixmap(pm)
        lay.addWidget(thumb)

        col = QVBoxLayout()
        col.setSpacing(4)
        title = QLabel(item.get("title") or item.get("name") or "未命名")
        title.setObjectName("histTitle")
        title.setWordWrap(True)
        title.setMaximumHeight(40)
        col.addWidget(title)

        meta = QLabel(
            f"视频长短 {item.get('video_dur_text', '未知')}"
            f"　·　下载耗时 {item.get('dl_dur_text', '未知')}"
            f"　·　{item.get('size_text', '')}"
        )
        meta.setObjectName("histMeta")
        col.addWidget(meta)

        when = QLabel(f"下载于 {item.get('when_text', '')}　·　{item.get('platform', '')}")
        when.setObjectName("histMeta")
        col.addWidget(when)
        col.addStretch(1)
        lay.addLayout(col, 1)

        btns = QVBoxLayout()
        btns.setSpacing(8)
        btns.addStretch(1)
        b_open = _make_button("打开文件", "ghost", 32, 88, lambda: on_open(item))
        b_del = _make_button("删除", "ghost", 32, 64, lambda: on_delete(item))
        btns.addWidget(b_open)
        btns.addWidget(b_del)
        btns.addStretch(1)
        lay.addLayout(btns)
        _add_shadow(self, blur=12, alpha=10, y=2)


class PreviewEmpty(QWidget):
    """虚线居中空状态预览区。"""

    def __init__(self):
        super().__init__()
        self.setObjectName("previewEmpty")
        self.setMinimumHeight(180)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(2, 2, -3, -3)
        p.setBrush(QColor(248, 250, 252))
        pen = QPen(QColor(DASH_BORDER), 1.4)
        pen.setStyle(Qt.DashLine)
        p.setPen(pen)
        p.drawRoundedRect(rect, 14, 14)
        p.end()


class PlayBadge(QWidget):
    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(219, 232, 252))
        p.drawEllipse(0, 0, self.width(), self.height())
        p.setBrush(QColor(PRIMARY))
        w, h = self.width(), self.height()
        p.drawPolygon(QPolygonF([
            QPointF(w * 0.40, h * 0.32), QPointF(w * 0.40, h * 0.68),
            QPointF(w * 0.68, h * 0.50),
        ]))
        p.end()


class VideoDownloaderWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("rootWin")
        self.setWindowTitle("视频下载器")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        # 全窗像素都由 paintEvent 负责（含透明圆角外），配合跳过 WM_ERASEBKGND 消 resize 闪烁
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setMinimumSize(1020, 700)
        self.resize(1280, 860)
        self._drag_pos = None

        self.config = core.load_config()
        core.ensure_dir(self.config["save_dir"])

        self.sig = DownloadSignals(self)
        self.sig.info.connect(self._on_info)
        self.sig.progress.connect(self._on_progress)
        self.sig.done.connect(self._on_done)
        self.sig.log.connect(self._append_log)
        self.sig.error.connect(self._on_error)
        self.sig.core_update.connect(self._on_update_done)

        self._dl = None
        self._thread = None
        self._nam = QNetworkAccessManager(self)
        self._history: list[dict] = []
        self._hist_path = os.path.join(self.config.get("save_dir") or ".",
                                       "download_history.json")
        self._thumb_dir = os.path.join(self.config.get("save_dir") or ".",
                                       "history_thumbs")
        core.ensure_dir(self._thumb_dir)
        self._load_history()
        self._pending_info: dict = {}
        self._dl_start_ts = 0.0
        self._thumb_cache_url = ""

        self._build_ui()
        self._apply_stylesheet()
        self.url_edit.setFocus()
        self._refresh_history_list()

        self._clip_timer = QTimer(self)
        self._clip_timer.timeout.connect(self._watch_clipboard)
        self._clip_timer.start(1500)
        self._startup_check()

    # ---------------- chrome ----------------
    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # Source 模式先清全窗（圆角外保持透明），避免 resize 时残留/闪白
        p.setCompositionMode(QPainter.CompositionMode_Source)
        p.fillRect(self.rect(), Qt.transparent)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        rect = self.rect().adjusted(0, 0, -1, -1)
        p.setPen(QPen(QColor(255, 255, 255, 70), 1))
        p.setBrush(QColor("#FFFFFF"))
        p.drawRoundedRect(rect, WINDOW_RADIUS, WINDOW_RADIUS)
        p.end()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton and ev.position().y() < TITLEBAR_H:
            self._drag_pos = ev.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, ev):
        if self._drag_pos is not None and ev.buttons() & Qt.LeftButton:
            self.move(ev.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, ev):
        self._drag_pos = None

    def nativeEvent(self, eventType, message):
        # 无边框窗口没有系统边框，用 WM_NCHITTEST 把边缘/角落交给系统缩放
        if eventType != b"windows_generic_MSG":
            return super().nativeEvent(eventType, message)
        import ctypes
        from ctypes import wintypes
        msg = wintypes.MSG.from_address(int(message))
        if msg.message == 0x0014:  # WM_ERASEBKGND：跳过系统擦背景，避免缩放/移动时闪
            return True, 1
        if msg.message == 0x0084 and not self.isMaximized():  # WM_NCHITTEST
            # lParam 是屏幕坐标（带符号，多显示器可能为负）
            x = ctypes.c_int16(msg.lParam & 0xFFFF).value
            y = ctypes.c_int16((msg.lParam >> 16) & 0xFFFF).value
            pos = self.mapFromGlobal(QPoint(x, y))
            m = 8
            left = pos.x() < m
            right = pos.x() >= self.width() - m
            top = pos.y() < m
            bottom = pos.y() >= self.height() - m
            if left and top:
                return True, 13          # HTTOPLEFT
            if right and top:
                return True, 14          # HTTOPRIGHT
            if left and bottom:
                return True, 16          # HTBOTTOMLEFT
            if right and bottom:
                return True, 17          # HTBOTTOMRIGHT
            if left:
                return True, 10          # HTLEFT
            if right:
                return True, 11          # HTRIGHT
            if top:
                return True, 12          # HTTOP
            if bottom:
                return True, 15          # HTBOTTOM
        return super().nativeEvent(eventType, message)

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(0)

        shell = QFrame()
        shell.setObjectName("shell")
        shell_lay = QVBoxLayout(shell)
        shell_lay.setContentsMargins(0, 0, 0, 0)
        shell_lay.setSpacing(0)

        shell_lay.addWidget(self._build_titlebar())
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_sidebar())
        body.addWidget(self._build_main())
        body_wrap = QWidget()
        body_wrap.setLayout(body)
        shell_lay.addWidget(body_wrap, 1)
        outer.addWidget(shell)

    def _build_titlebar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("titleBar")
        bar.setFixedHeight(TITLEBAR_H)
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(12, 0, 0, 0)
        lay.setSpacing(10)

        logo = QLabel()
        logo.setPixmap(_icon_app_box(28).pixmap(28, 28))
        logo.setFixedSize(28, 28)
        lay.addWidget(logo)
        title = QLabel("视频下载器")
        title.setObjectName("winTitle")
        lay.addWidget(title)
        lay.addStretch(1)

        self.cap_min = CapButton("min")
        self.cap_max = CapButton("max")
        self.cap_close = CapButton("close")
        self.cap_close.setToolTip("关闭")
        self.cap_min.clicked.connect(self.showMinimized)
        self.cap_max.clicked.connect(self._toggle_max)
        self.cap_close.clicked.connect(self.close)
        lay.addWidget(self.cap_min)
        lay.addWidget(self.cap_max)
        lay.addWidget(self.cap_close)
        return bar

    def _toggle_max(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def _build_sidebar(self) -> QWidget:
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(SIDEBAR_W)
        lay = QVBoxLayout(side)
        lay.setContentsMargins(12, 16, 12, 16)
        lay.setSpacing(8)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.navs: dict[str, NavButton] = {}
        for key, label, icon in (
            ("home", "首页", "home"),
            ("tasks", "下载任务", "down"),
            ("done", "已完成", "check"),
            ("about", "关于", "info"),
        ):
            btn = NavButton(label, icon, key)
            self.nav_group.addButton(btn)
            self.navs[key] = btn
            lay.addWidget(btn)
        self.navs["home"].setChecked(True)
        self.nav_group.buttonClicked.connect(self._on_nav)

        lay.addStretch(1)
        self.btn_side_settings = NavButton("设置", "gear", "settings")
        self.btn_side_settings.setCheckable(False)
        self.btn_side_settings.clicked.connect(self._open_settings)
        lay.addWidget(self.btn_side_settings)
        return side

    def _build_main(self) -> QWidget:
        main = QFrame()
        main.setObjectName("mainArea")
        lay = QVBoxLayout(main)
        lay.setContentsMargins(24, 18, 24, 18)
        lay.setSpacing(14)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._build_home_page())
        self.pages.addWidget(self._build_tasks_page())
        self.pages.addWidget(self._build_done_page())
        self.pages.addWidget(self._build_about_page())
        lay.addWidget(self.pages, 1)
        return main

    def _build_home_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("pageHome")
        outer = QVBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(14)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setObjectName("pageScroll")
        body = QWidget()
        body.setObjectName("pageBody")
        lay = QVBoxLayout(body)
        lay.setContentsMargins(4, 4, 10, 8)
        lay.setSpacing(14)

        lay.addLayout(self._build_header())
        lay.addWidget(self._build_link_card())
        lay.addWidget(self._build_download_settings_card())
        lay.addWidget(self._build_preview_card())
        lay.addLayout(self._build_actions())
        lay.addWidget(self._build_log_card())
        lay.addStretch(1)
        scroll.setWidget(body)
        outer.addWidget(scroll)
        return page

    def _build_header(self):
        row = QHBoxLayout()
        row.setSpacing(14)
        row.setContentsMargins(4, 2, 4, 2)
        icon = QLabel()
        icon.setPixmap(_icon_app_box(56).pixmap(56, 56))
        icon.setFixedSize(58, 58)
        row.addWidget(icon)
        col = QVBoxLayout()
        col.setSpacing(2)
        title = QLabel("视频下载器")
        title.setObjectName("appTitle")
        sub = QLabel("支持 YouTube / B站 / 抖音 等主流平台  ·  简单  ·  快速  ·  稳定")
        sub.setObjectName("appSubtitle")
        col.addWidget(title)
        col.addWidget(sub)
        row.addLayout(col)
        row.addStretch(1)

        self.btn_update = _make_button("  更新核心", "ghost", 36, on_click=self._update_core,
                                       icon=_icon_glyph("refresh", TEXT_BODY, 18))
        self.btn_settings = _make_button("  设置", "ghost", 36, on_click=self._open_settings,
                                         icon=_icon_glyph("gear", TEXT_BODY, 18))
        # 设计稿顺序：更新核心 在左，设置 在右
        row.addWidget(self.btn_update)
        row.addWidget(self.btn_settings)
        return row

    def _build_link_card(self):
        card = _make_card()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(12)
        row = QHBoxLayout()
        row.setSpacing(10)
        self.url_edit = QLineEdit()
        self.url_edit.setObjectName("urlEdit")
        self.url_edit.setPlaceholderText("粘贴视频链接或分享文案（支持 YouTube / B站 / 抖音 等）")
        self.url_edit.setFixedHeight(48)
        self.url_edit.addAction(_icon_glyph("link", TEXT_MUTED, 18), QLineEdit.LeadingPosition)
        self.url_edit.returnPressed.connect(self._start_download)
        row.addWidget(self.url_edit, 1)
        self.btn_paste = _make_button("  粘贴", "primary", 48, 108, self._paste_from_clipboard,
                                      icon=_icon_glyph("clipboard", "#FFFFFF", 18))
        row.addWidget(self.btn_paste)
        lay.addLayout(row)

        hint = QHBoxLayout()
        hint.setSpacing(8)
        spark = QLabel()
        spark.setPixmap(_icon_glyph("sparkle", PRIMARY, 16).pixmap(16, 16))
        spark.setFixedSize(16, 16)
        hint.addWidget(spark, 0, Qt.AlignVCenter)
        self.clip_hint = QLabel("检测到剪贴板内容？")
        self.clip_hint.setObjectName("hintText")
        hint.addWidget(self.clip_hint, 0, Qt.AlignVCenter)
        self.btn_clip_try = QPushButton("粘贴试试")
        self.btn_clip_try.setObjectName("linkBtn")
        self.btn_clip_try.setCursor(Qt.PointingHandCursor)
        self.btn_clip_try.clicked.connect(self._paste_from_clipboard)
        hint.addWidget(self.btn_clip_try, 0, Qt.AlignVCenter)
        hint.addStretch(1)
        lay.addLayout(hint)
        return card

    def _build_download_settings_card(self):
        card = _make_card()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 14, 18, 16)
        lay.setSpacing(14)

        head = QHBoxLayout()
        head.setSpacing(8)
        gi = QLabel()
        gi.setPixmap(_icon_glyph("gear", TEXT_TITLE, 18).pixmap(18, 18))
        gi.setFixedSize(18, 18)
        head.addWidget(gi)
        t = QLabel("下载设置")
        t.setObjectName("cardTitleLg")
        head.addWidget(t)
        head.addStretch(1)
        lay.addLayout(head)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 2)
        grid.setColumnStretch(2, 2)
        grid.setColumnStretch(3, 2)

        def label(text, icon_kind):
            row = QHBoxLayout()
            row.setSpacing(8)
            row.setContentsMargins(0, 0, 0, 0)
            ic = QLabel()
            ic.setPixmap(_icon_glyph(icon_kind, TEXT_LABEL, 16).pixmap(16, 16))
            ic.setFixedSize(18, 18)
            ic.setScaledContents(True)
            row.addWidget(ic, 0, Qt.AlignVCenter)
            t = QLabel("  " + text)  # 空格垫开，避免图标压字
            t.setObjectName("fieldLabel")
            row.addWidget(t, 0, Qt.AlignVCenter)
            row.addStretch(1)
            w = QWidget()
            w.setLayout(row)
            w.setFixedHeight(20)
            return w

        # 第一行：四个标签等高、顶对齐
        grid.addWidget(label("保存路径", "folder"), 0, 0, Qt.AlignTop)
        grid.addWidget(label("格式", "format"), 0, 1, Qt.AlignTop)
        grid.addWidget(label("清晰度", "quality"), 0, 2, Qt.AlignTop)
        grid.addWidget(label("网络代理", "globe"), 0, 3, Qt.AlignTop)

        # 第二行：控件等高 42
        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        path_row.setContentsMargins(0, 0, 0, 0)
        self.path_edit = QLineEdit(self.config["save_dir"])
        self.path_edit.setObjectName("pathEdit")
        self.path_edit.setReadOnly(True)
        self.path_edit.setFixedHeight(42)
        self.path_edit.setFocusPolicy(Qt.NoFocus)
        path_row.addWidget(self.path_edit, 1)
        path_row.addWidget(_make_button("更改", "secondary", 42, 64, self._change_save_dir))
        path_wrap = QWidget()
        path_wrap.setFixedHeight(42)
        path_wrap.setLayout(path_row)
        grid.addWidget(path_wrap, 1, 0)

        self.cb_format = _make_combo(FORMAT_ITEMS, self.config.get("default_format", "mp4"))
        grid.addWidget(self.cb_format, 1, 1)

        self.cb_quality = _make_combo(QUALITY_ITEMS, self.config.get("default_quality", "best"))
        grid.addWidget(self.cb_quality, 1, 2)

        self.cb_proxy = _make_combo(PROXY_ITEMS, self.config.get("proxy_mode", "auto"))
        grid.addWidget(self.cb_proxy, 1, 3)

        self.cb_format.currentIndexChanged.connect(self._sync_ui_to_config)
        self.cb_quality.currentIndexChanged.connect(self._sync_ui_to_config)
        self.cb_proxy.currentIndexChanged.connect(self._sync_ui_to_config)
        lay.addLayout(grid)
        return card

    def _build_preview_card(self):
        wrap = QWidget()
        outer = QVBoxLayout(wrap)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)

        self.preview_empty = PreviewEmpty()
        inner = QVBoxLayout(self.preview_empty)
        inner.setContentsMargins(24, 22, 24, 18)
        inner.setSpacing(8)

        # 上半：播放徽标 + 标题（居中）；有信息后切换为缩略图布局
        self.preview_stack = QVBoxLayout()
        self.preview_stack.setSpacing(6)

        center = QVBoxLayout()
        center.setSpacing(8)
        self.play_badge = PlayBadge()
        self.play_badge.setFixedSize(56, 56)
        center.addWidget(self.play_badge, 0, Qt.AlignHCenter)

        self.info_title = QLabel("等待链接")
        self.info_title.setObjectName("previewTitle")
        self.info_title.setAlignment(Qt.AlignCenter)
        center.addWidget(self.info_title)

        self.info_sub = QLabel("粘贴链接后这里会显示视频标题、时长和大小")
        self.info_sub.setObjectName("infoSub")
        self.info_sub.setAlignment(Qt.AlignCenter)
        self.info_sub.setWordWrap(True)
        center.addWidget(self.info_sub)

        # 有数据后用的横排缩略图（默认隐藏）
        self.thumb_row = QWidget()
        thumb_lay = QHBoxLayout(self.thumb_row)
        thumb_lay.setContentsMargins(0, 0, 0, 0)
        thumb_lay.setSpacing(16)
        self.thumb = QLabel()
        self.thumb.setObjectName("thumb")
        self.thumb.setFixedSize(180, 102)
        self.thumb.setVisible(False)
        thumb_lay.addWidget(self.thumb)
        info_col = QVBoxLayout()
        info_col.setSpacing(6)
        self.meta_label = QLabel("")
        self.meta_label.setObjectName("infoSub")
        self.meta_label.setWordWrap(True)
        info_col.addWidget(self.meta_label)
        self.chip_label = QLabel("")
        self.chip_label.setObjectName("chipLine")
        info_col.addWidget(self.chip_label)
        info_col.addStretch(1)
        thumb_lay.addLayout(info_col, 1)
        self.thumb_row.setVisible(False)

        self.preview_stack.addLayout(center)
        self.preview_stack.addWidget(self.thumb_row)
        inner.addLayout(self.preview_stack, 1)

        prog = QHBoxLayout()
        prog.setSpacing(12)
        self.progress = QProgressBar()
        self.progress.setObjectName("progress")
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFixedHeight(8)
        self.progress.setTextVisible(False)
        prog.addWidget(self.progress, 1)
        self.percent_label = QLabel("0.0%")
        self.percent_label.setObjectName("percentText")
        self.percent_label.setFixedWidth(48)
        self.percent_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        prog.addWidget(self.percent_label)
        inner.addLayout(prog)

        self.status_label = QLabel("就绪 · 等待链接")
        self.status_label.setObjectName("statusText")
        self.status_label.setAlignment(Qt.AlignCenter)
        inner.addWidget(self.status_label)

        outer.addWidget(self.preview_empty, 1)
        return wrap

    def _build_actions(self):
        row = QHBoxLayout()
        row.setContentsMargins(4, 0, 4, 0)
        row.setSpacing(12)
        self.btn_download = _make_button("  开始下载", "primary", 48, 168, self._start_download,
                                         icon=_icon_glyph("down", "#FFFFFF", 18))
        row.addWidget(self.btn_download)
        self.btn_stop = _make_button("  暂停", "secondary", 48, 128, self._stop_download,
                                     icon=_icon_glyph("pause", TEXT_LABEL, 18))
        self.btn_stop.setEnabled(False)
        row.addWidget(self.btn_stop)
        row.addStretch(1)
        self.btn_tasks = QPushButton("任务列表  ›")
        self.btn_tasks.setObjectName("linkBtn")
        self.btn_tasks.setCursor(Qt.PointingHandCursor)
        self.btn_tasks.clicked.connect(lambda: self._switch_nav("tasks"))
        row.addWidget(self.btn_tasks)
        return row

    def _build_log_card(self):
        card = _make_card()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(10)
        head = QHBoxLayout()
        head.setSpacing(8)
        icon = QLabel()
        icon.setPixmap(_icon_glyph("doc", TEXT_BODY, 18).pixmap(18, 18))
        icon.setFixedSize(18, 18)
        head.addWidget(icon)
        t = QLabel("下载日志")
        t.setObjectName("cardTitle")
        head.addWidget(t)
        head.addStretch(1)
        self.btn_clear_log = _make_button("清空", "ghost", 28, 56, self._clear_log)
        head.addWidget(self.btn_clear_log)
        chev = QLabel()
        chev.setPixmap(_icon_glyph("chevron_up", TEXT_MUTED, 16).pixmap(16, 16))
        head.addWidget(chev)
        lay.addLayout(head)
        self.log_edit = _LogView()
        self.log_edit.setObjectName("logEdit")
        self.log_edit.setReadOnly(True)
        self.log_edit.setMinimumHeight(100)
        lay.addWidget(self.log_edit, 1)
        return card

    def _build_tasks_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        title = QLabel("下载任务")
        title.setObjectName("pageTitle")
        lay.addWidget(title)
        self.tasks_list = QLabel("暂无进行中的任务。\n在「首页」粘贴链接并开始下载后，会显示在这里。")
        self.tasks_list.setObjectName("emptyHint")
        self.tasks_list.setWordWrap(True)
        self.tasks_list.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.tasks_list, 1)
        return page

    def _build_done_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        head = QHBoxLayout()
        title = QLabel("已完成")
        title.setObjectName("pageTitle")
        head.addWidget(title)
        head.addStretch(1)
        self.btn_clear_hist = _make_button("清空记录", "ghost", 32, 88, self._clear_history)
        head.addWidget(self.btn_clear_hist)
        lay.addLayout(head)

        self.hist_empty = QLabel("还没有完成的下载。\n下载成功的视频会显示在这里：封面、时长、下载耗时、时间，可删除记录。")
        self.hist_empty.setObjectName("emptyHint")
        self.hist_empty.setWordWrap(True)
        self.hist_empty.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.hist_empty)

        self.hist_scroll = QScrollArea()
        self.hist_scroll.setWidgetResizable(True)
        self.hist_scroll.setFrameShape(QFrame.NoFrame)
        self.hist_scroll.setObjectName("histScroll")
        self.hist_list = QWidget()
        self.hist_list.setObjectName("histList")
        self.hist_list_lay = QVBoxLayout(self.hist_list)
        self.hist_list_lay.setContentsMargins(0, 0, 8, 0)
        self.hist_list_lay.setSpacing(10)
        self.hist_list_lay.addStretch(1)
        self.hist_scroll.setWidget(self.hist_list)
        lay.addWidget(self.hist_scroll, 1)
        return page

    def _build_about_page(self):
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(14)

        # 与首页一致的品牌头
        head = QHBoxLayout()
        head.setSpacing(14)
        icon = QLabel()
        icon.setPixmap(_icon_app_box(56).pixmap(56, 56))
        icon.setFixedSize(58, 58)
        head.addWidget(icon)
        col = QVBoxLayout()
        col.setSpacing(2)
        t1 = QLabel("视频下载器")
        t1.setObjectName("appTitle")
        t2 = QLabel("基于 yt-dlp · 轻量、稳定、好用")
        t2.setObjectName("appSubtitle")
        col.addWidget(t1)
        col.addWidget(t2)
        head.addLayout(col)
        head.addStretch(1)
        ver = QLabel("v1.0")
        ver.setObjectName("hintText")
        head.addWidget(ver, 0, Qt.AlignBottom)
        lay.addLayout(head)

        # 功能说明卡
        card = _make_card()
        cl = QVBoxLayout(card)
        cl.setContentsMargins(20, 16, 20, 16)
        cl.setSpacing(8)

        feat_title = QLabel("功能说明")
        feat_title.setObjectName("cardTitleLg")
        cl.addWidget(feat_title)
        feats = QLabel(
            "· 粘贴链接或分享文案即可下载 YouTube / B站 / 抖音 等\n"
            "· 格式：MP4 / WebM / MP3（仅音频）\n"
            "· 自动优先 H.264 + AAC，必要时兼容转码\n"
            "· 下载历史：封面、时长、耗时、时间，可删除记录"
        )
        feats.setObjectName("aboutBody")
        feats.setWordWrap(True)
        cl.addWidget(feats)
        lay.addWidget(card)

        # 联系方式卡
        ccard = _make_card()
        cc = QVBoxLayout(ccard)
        cc.setContentsMargins(20, 16, 20, 16)
        cc.setSpacing(12)

        ct = QLabel("作者联系方式")
        ct.setObjectName("cardTitleLg")
        cc.addWidget(ct)

        for label_text, value_text, icon_kind in (
            ("QQ", "36306441002", "info"),
            ("抖音号", "48171030985", "play"),
        ):
            row = QHBoxLayout()
            row.setSpacing(12)
            tag = QLabel(label_text)
            tag.setObjectName("aboutTag")
            tag.setFixedWidth(64)
            tag.setAlignment(Qt.AlignCenter)
            row.addWidget(tag)
            val = QLabel(value_text)
            val.setObjectName("aboutContact")
            row.addWidget(val)
            row.addStretch(1)
            wrap = QWidget()
            wrap.setLayout(row)
            cc.addWidget(wrap)

        tip = QLabel("仅供个人学习与备份使用，请遵守平台服务条款与版权法规。")
        tip.setObjectName("hintText")
        tip.setWordWrap(True)
        cc.addWidget(tip)
        lay.addWidget(ccard)

        lay.addStretch(1)
        return page

    # ---------------- QSS ----------------
    def _apply_stylesheet(self):
        arrow_pm = QPixmap(16, 16)
        arrow_pm.fill(Qt.transparent)
        ap = QPainter(arrow_pm)
        ap.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(TEXT_LABEL), 1.6)
        pen.setCapStyle(Qt.RoundCap)
        ap.setPen(pen)
        ap.drawLine(QPointF(4, 6.5), QPointF(8, 10.5))
        ap.drawLine(QPointF(8, 10.5), QPointF(12, 6.5))
        ap.end()
        arrow_path = os.path.join(os.environ.get("TEMP", "."), "videodl_arrow.png")
        arrow_pm.save(arrow_path, "PNG")
        arrow = arrow_path.replace("\\", "/")

        self.setStyleSheet(f"""
            * {{ font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif; }}
            #shell {{
                background: #FFFFFF;
                border: 1px solid #E8EEF6;
                border-radius: {WINDOW_RADIUS}px;
            }}
            #titleBar {{
                background: #FFFFFF;
                border-top-left-radius: {WINDOW_RADIUS}px;
                border-top-right-radius: {WINDOW_RADIUS}px;
                border-bottom: 1px solid #EEF2F7;
            }}
            #winTitle {{ font-size: 13px; font-weight: 600; color: {TEXT_TITLE}; }}
            #sidebar {{
                background: #F0F4FA;
                border-bottom-left-radius: {WINDOW_RADIUS}px;
            }}
            #brandName {{ font-size: 15px; font-weight: 700; color: {TEXT_TITLE}; }}
            #mainArea {{ background: #FFFFFF; border-bottom-right-radius: {WINDOW_RADIUS}px; }}
            #pageHome, #pageBody, QScrollArea#pageScroll, QScrollArea#pageScroll > QWidget > QWidget,
            QWidget#pageBody, QWidget#pageHome {{
                background: #FFFFFF; border: none;
            }}

            QPushButton#navBtn {{
                text-align: left; padding: 0 14px; border: none; border-radius: 10px;
                color: #3D4A5C; font-size: 13px; background: transparent; font-weight: 500;
            }}
            QPushButton#navBtn:hover {{ background: rgba(59,130,246,0.10); }}
            QPushButton#navBtn:checked {{ background: #DCEBFF; color: #1D4ED8; font-weight: 700; }}

            #card {{
                background: {CARD_BG};
                border: 1px solid {BORDER};
                border-radius: {CARD_RADIUS}px;
            }}
            #appTitle {{ font-size: 26px; font-weight: 700; color: {TEXT_TITLE}; }}
            #appSubtitle {{ font-size: 13px; color: {TEXT_BODY}; }}
            #pageTitle {{ font-size: 22px; font-weight: 700; color: {TEXT_TITLE}; margin: 8px 4px; }}
            #cardTitle {{ font-size: 15px; font-weight: 650; color: {TEXT_TITLE}; }}
            #cardTitleLg {{ font-size: 16px; font-weight: 700; color: {TEXT_TITLE}; }}
            #fieldLabel {{ font-size: 13px; color: {TEXT_LABEL}; font-weight: 500; }}
            #previewTitle {{ font-size: 18px; font-weight: 700; color: {TEXT_TITLE}; }}
            #infoSub {{ font-size: 13px; color: #5B7BA8; }}
            #chipLine {{ font-size: 12px; color: {TEXT_MUTED}; }}
            #statusText {{ font-size: 12px; color: {TEXT_BODY}; }}
            #percentText {{ font-size: 12px; font-weight: 600; color: {TEXT_BODY}; }}
            #hintText {{ font-size: 12px; color: #7A8BA3; background: transparent; }}
            #emptyHint {{ font-size: 14px; color: {TEXT_MUTED}; padding: 40px; }}
            #aboutBody {{ font-size: 13px; color: {TEXT_BODY}; line-height: 1.55; }}
            #aboutContact {{ font-size: 16px; color: {TEXT_TITLE}; font-weight: 700; }}
            #aboutTag {{
                background: {PRIMARY_SOFT}; color: {PRIMARY_HOVER};
                border-radius: 8px; padding: 4px 0; font-size: 12px; font-weight: 700;
            }}
            #hSep {{ color: {BORDER}; }}
            #histCard {{ background: {CARD_BG}; border: 1px solid {BORDER}; border-radius: 14px; }}
            #histThumb {{ border-radius: 10px; border: 1px solid {BORDER}; background: #E8EEF5; }}
            #histTitle {{ font-size: 14px; font-weight: 650; color: {TEXT_TITLE}; }}
            #histMeta {{ font-size: 12px; color: {TEXT_LABEL}; }}
            #histScroll, QWidget#histList {{ background: transparent; border: none; }}

            QLineEdit {{
                background: #FFFFFF;
                border: 1px solid {FIELD_BORDER};
                border-radius: 10px;
                padding: 0 12px;
                color: {TEXT_TITLE};
                font-size: 13px;
                selection-background-color: {PRIMARY};
                selection-color: white;
            }}
            #urlEdit {{ border-radius: 12px; font-size: 14px; }}
            QLineEdit:hover {{ border-color: #B8C4D4; }}
            QLineEdit:focus {{ border: 1px solid {PRIMARY}; }}
            QLineEdit[readOnly="true"] {{ background: #F5F7FB; color: {TEXT_BODY}; }}
            QLineEdit:disabled {{ color: {TEXT_MUTED}; background: #F5F7FB; }}
            #customSelect {{ background: transparent; }}

            QPushButton {{
                background: white; color: {TEXT_TITLE};
                border: 1px solid {FIELD_BORDER}; border-radius: 10px;
                padding: 0 16px; font-size: 13px; font-weight: 500;
            }}
            QPushButton:hover {{ background: #F8FAFC; border-color: #B8C4D4; }}
            QPushButton:disabled {{ color: {TEXT_MUTED}; background: #F5F7FB; border-color: {BORDER}; }}
            QPushButton#primary {{
                background: {PRIMARY}; border: 1px solid {PRIMARY};
                color: white; font-weight: 600; font-size: 14px;
            }}
            QPushButton#primary:hover {{ background: {PRIMARY_HOVER}; border-color: {PRIMARY_HOVER}; }}
            QPushButton#primary:pressed {{ background: {PRIMARY_PRESSED}; }}
            QPushButton#primary:disabled {{ background: #BFDBFE; border-color: #BFDBFE; color: white; }}
            QPushButton#ghost {{
                background: transparent; border: 1px solid transparent; color: {TEXT_BODY};
                padding: 0 12px;
            }}
            QPushButton#ghost:hover {{ background: rgba(15,23,42,0.05); }}
            QPushButton#linkBtn {{
                background: transparent; border: none; color: {LINK};
                font-size: 13px; font-weight: 500; padding: 0 4px;
            }}
            QPushButton#linkBtn:hover {{ color: {PRIMARY_HOVER}; text-decoration: underline; }}
            QCheckBox {{ color: {TEXT_BODY}; font-size: 13px; spacing: 8px; }}

            QProgressBar {{ background: #E2EAF4; border: none; border-radius: 4px; min-height: 8px; }}
            QProgressBar::chunk {{ background: #B7C7DE; border-radius: 4px; }}

            #thumb {{ border-radius: 12px; border: 1px solid {BORDER}; }}
            #logEdit {{
                background: {LOG_BG}; color: {LOG_TEXT};
                border: 1px solid {BORDER}; border-radius: 12px;
                padding: 10px 12px;
                font-family: "Cascadia Mono", "Consolas", "Courier New", monospace;
                font-size: 12px;
            }}
            QScrollBar:vertical {{ background: transparent; width: 10px; }}
            QScrollBar::handle:vertical {{ background: #CBD5E1; border-radius: 5px; min-height: 24px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

    # ---------------- 交互 ----------------
    def _on_nav(self, btn: NavButton):
        self._switch_nav(btn.key)

    def _switch_nav(self, key: str):
        order = {"home": 0, "tasks": 1, "done": 2, "about": 3}
        self.pages.setCurrentIndex(order.get(key, 0))
        if key in self.navs:
            self.navs[key].setChecked(True)

    def _watch_clipboard(self):
        pass

    def _clear_log(self):
        self.log_edit.clear()

    def _append_log(self, msg: str):
        if msg.startswith(("[错误", "[失败")):
            color = "#C0362C"
        elif msg.startswith("[警告"):
            color = "#9A6200"
        elif msg.startswith("[完成"):
            color = "#12794A"
        else:
            color = LOG_TEXT
        ts = datetime.now().strftime("%H:%M:%S")
        cur = self.log_edit.textCursor()
        cur.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cur.insertText(f"[{ts}] {msg}\n", fmt)
        self.log_edit.setTextCursor(cur)
        self.log_edit.ensureCursorVisible()
        m = SPEED_RE.search(msg)
        m2 = ETA_RE.search(msg)
        if m or m2:
            parts = []
            if m:
                parts.append(f"↓ {m.group(1)}")
            if m2:
                parts.append(f"剩余 {m2.group(1)}")
            self.status_label.setText("下载中 · " + " · ".join(parts))

    def _startup_check(self):
        err = core.check_ytdlp()
        if err:
            self._append_log(f"[警告] {err}")
        ffmpeg = core.find_ffmpeg(self.config)
        if ffmpeg:
            self._append_log(f"[信息] ffmpeg 已找到：{ffmpeg}")
        else:
            w = core.check_ffmpeg(self.config)
            if w:
                self._append_log(f"[警告] {w}")

    def _paste_from_clipboard(self):
        text = QApplication.clipboard().text()
        url = core.extract_url_from_text(text)
        if url:
            self.url_edit.setText(url)
            self.url_edit.setFocus()
        else:
            QMessageBox.warning(self, "剪贴板", "剪贴板内容不是有效链接。")

    def _change_save_dir(self):
        new_dir = QFileDialog.getExistingDirectory(self, "选择保存目录", self.config["save_dir"])
        if not new_dir:
            return
        self.config["save_dir"] = new_dir
        self.path_edit.setText(new_dir)
        core.ensure_dir(new_dir)
        core.save_config(self.config)

    def _open_settings(self):
        SettingsDialog(self, self.config, self._on_settings_saved).exec()

    def _on_settings_saved(self, cfg: dict):
        self.config = cfg
        idx = self.cb_proxy.findData(cfg["proxy_mode"])
        if idx >= 0 and idx != self.cb_proxy.currentIndex():
            self.cb_proxy.blockSignals(True)
            self.cb_proxy.setCurrentIndex(idx)
            self.cb_proxy.blockSignals(False)
        self._append_log("[设置] 配置已更新")

    def _sync_ui_to_config(self):
        self.config["default_format"] = self.cb_format.currentData() or "mp4"
        self.config["default_quality"] = self.cb_quality.currentData() or "best"
        self.config["proxy_mode"] = self.cb_proxy.currentData() or "auto"
        core.save_config(self.config)

    def _set_preview_mode(self, has_info: bool):
        self.play_badge.setVisible(not has_info)
        self.thumb_row.setVisible(has_info)
        self.thumb.setVisible(has_info)
        if has_info:
            self.info_title.setAlignment(Qt.AlignLeft)
            self.info_sub.setAlignment(Qt.AlignLeft)

    def _start_download(self):
        url = core.extract_url_from_text(self.url_edit.text())
        if not url:
            self._append_log("[提示] 请先粘贴视频链接（或含链接的分享文案）。")
            return
        self.url_edit.setText(url)
        err = core.check_ytdlp()
        if err:
            self._append_log(f"[错误] {err}")
            QMessageBox.critical(self, "依赖缺失", err)
            return
        self._sync_ui_to_config()
        self._set_ui_state(False)
        self._dl_start_ts = time.time()
        self._pending_info = {}

        folder_name, target_dir = core.get_today_folder(self.config["save_dir"])
        core.ensure_dir(target_dir)
        ext = core.output_ext(self.config.get("default_format", "mp4"),
                              self.config.get("default_quality", "best"))
        output_path = core.get_next_filepath(target_dir, folder_name, ext=ext)
        ffmpeg_path = core.find_ffmpeg(self.config)

        self.progress.setValue(0)
        self.percent_label.setText("0.0%")
        self.status_label.setText("正在获取视频信息…")
        self.info_title.setText("正在获取视频信息…")
        self.info_title.setAlignment(Qt.AlignCenter)
        self.info_sub.setText("请稍候")
        self.info_sub.setAlignment(Qt.AlignCenter)
        self._set_preview_mode(False)

        self._dl = core.Downloader(
            url=url, output_path=output_path, config=self.config,
            ffmpeg_path=ffmpeg_path,
            info_cb=self.sig.info.emit, progress_cb=self.sig.progress.emit,
            done_cb=self.sig.done.emit, log_cb=self.sig.log.emit,
            error_cb=self.sig.error.emit,
        )
        self._thread = threading.Thread(target=self._dl.run, daemon=True)
        self._thread.start()

    def _on_info(self, info: dict):
        title = info.get("title", "?")
        uploader = info.get("uploader", "?")
        duration = info.get("duration", 0)
        resolution = info.get("resolution", "?")
        platform = info.get("platform", "?")
        size = info.get("filesize", 0)

        self._pending_info = {
            "title": title,
            "uploader": uploader,
            "duration": duration or 0,
            "platform": platform,
            "filesize": size or 0,
            "thumbnail": info.get("thumbnail", "") or "",
        }

        self._set_preview_mode(True)
        self.info_title.setText(title)
        self.info_title.setAlignment(Qt.AlignLeft)
        self.info_sub.setText(f"{uploader}　·　{resolution}")
        self.info_sub.setAlignment(Qt.AlignLeft)
        self.meta_label.setText(
            f"时长 {self._fmt_duration(duration)}　·　预计 {self._fmt_size(size)}　·　{platform}")
        self.chip_label.setText("可开始下载 · 优先 H.264 + AAC")
        self.status_label.setText("已获取信息 · 可开始下载")
        if self._dl is not None:
            self._append_log(f"[信息] 文件：{os.path.basename(self._dl.output_path)}")
        thumb_url = info.get("thumbnail", "")
        if thumb_url:
            self._thumb_cache_url = thumb_url
            self._load_thumbnail(thumb_url)

    @staticmethod
    def _fmt_duration(seconds):
        if not seconds:
            return "未知"
        seconds = int(seconds)
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

    @staticmethod
    def _fmt_size(n):
        if not n:
            return "未知"
        n = float(n)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if n < 1024:
                return f"{n:.1f} {unit}"
            n /= 1024
        return f"{n:.1f} PB"

    def _load_thumbnail(self, url):
        try:
            reply = self._nam.get(QNetworkRequest(QUrl(url)))
            reply.finished.connect(lambda: self._on_thumb_done(reply))
        except Exception:
            pass

    def _on_thumb_done(self, reply):
        data = reply.readAll()
        reply.deleteLater()
        pm = QPixmap()
        if pm.loadFromData(data):
            self.thumb.setPixmap(pm.scaled(180, 102, Qt.KeepAspectRatioByExpanding,
                                           Qt.SmoothTransformation))

    def _on_progress(self, pct: float):
        self.progress.setValue(int(pct))
        self.percent_label.setText(f"{pct:.1f}%")

    def _on_error(self, report: dict):
        category = report.get("category", "未知错误")
        self.status_label.setText(f"已失败 · {category}")
        QMessageBox.critical(
            self, "下载失败诊断",
            f"【{category}】\n\n原因：{report.get('reason','')}\n\n建议：{report.get('solution','')}")

    def _on_done(self, ok: bool, msg: str):
        self._set_ui_state(True)
        if ok:
            self.progress.setValue(100)
            self.percent_label.setText("100.0%")
            self.status_label.setText("已完成")
            self._append_log(f"[完成] {msg}")
            path = self._dl.output_path if self._dl else ""
            self._append_history(path, msg)
            self.tasks_list.setText("当前没有进行中的任务。")
            self.url_edit.clear()
            self.url_edit.setFocus()
            if self.config.get("auto_open_folder", True):
                _, folder_path = core.get_today_folder(self.config["save_dir"])
                try:
                    os.startfile(folder_path)
                except Exception:
                    pass
        else:
            stopped = ("停止" in msg) or ("取消" in msg) or ("暂停" in msg)
            self.status_label.setText("已暂停 · 可以重新开始" if stopped else "已失败 · 见诊断提示")
            self._append_log(f"{'[提示]' if stopped else '[失败]'} {msg}")

    # ---------------- 下载历史 ----------------
    def _load_history(self):
        try:
            if os.path.isfile(self._hist_path):
                self._history = json.loads(open(self._hist_path, encoding="utf-8").read()) or []
        except Exception:
            self._history = []

    def _save_history(self):
        try:
            with open(self._hist_path, "w", encoding="utf-8") as f:
                json.dump(self._history, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _cache_thumb(self) -> str:
        """把预览缩略图落到本地，历史卡片用。"""
        if not self._thumb_cache_url:
            return ""
        try:
            safe = re.sub(r"[^\w.-]", "_", self._thumb_cache_url)[-80:]
            path = os.path.join(self._thumb_dir, safe if safe.endswith(
                (".jpg", ".jpeg", ".png", ".webp")) else safe + ".jpg")
            if os.path.isfile(path):
                return path
            reply = self._nam.get(QNetworkRequest(QUrl(self._thumb_cache_url)))
            holder = {"done": False}

            def _fin(r=reply, p=path, h=holder):
                data = r.readAll()
                r.deleteLater()
                try:
                    open(p, "wb").write(bytes(data))
                except Exception:
                    return
                h["done"] = True

            reply.finished.connect(_fin)
            # 同步等 2 秒左右，历史立刻可见；慢网下次再补
            t0 = time.time()
            while not holder["done"] and time.time() - t0 < 2.0:
                QApplication.processEvents()
                time.sleep(0.02)
            return path if os.path.isfile(path) else ""
        except Exception:
            return ""

    def _append_history(self, path: str, msg: str):
        info = self._pending_info or {}
        name = os.path.basename(path) if path else ""
        size = 0
        try:
            if path and os.path.isfile(path):
                size = os.path.getsize(path)
        except Exception:
            pass
        dl_secs = max(0.0, time.time() - self._dl_start_ts) if self._dl_start_ts else 0.0
        thumb_path = self._cache_thumb()
        item = {
            "id": uuid.uuid4().hex,
            "title": info.get("title") or name or "未命名",
            "name": name,
            "path": path or "",
            "thumb_path": thumb_path,
            "thumb_url": info.get("thumbnail", ""),
            "video_duration": int(info.get("duration") or 0),
            "video_dur_text": self._fmt_duration(info.get("duration") or 0),
            "download_secs": dl_secs,
            "dl_dur_text": self._fmt_duration(dl_secs) if dl_secs >= 1 else f"{dl_secs:.1f}s",
            "size": size or int(info.get("filesize") or 0),
            "size_text": self._fmt_size(size or info.get("filesize") or 0),
            "platform": info.get("platform") or "",
            "when": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "when_text": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "msg": msg,
        }
        self._history.insert(0, item)
        self._save_history()
        self._refresh_history_list()

    def _refresh_history_list(self):
        if not hasattr(self, "hist_list"):
            return
        # 清掉旧卡片（保留 stretch）
        while self.hist_list_lay.count():
            it = self.hist_list_lay.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        has = bool(self._history)
        self.hist_empty.setVisible(not has)
        self.hist_scroll.setVisible(has)
        for item in self._history:
            self.hist_list_lay.addWidget(
                HistoryCard(item, self._delete_history_item, self._open_history_file))
        self.hist_list_lay.addStretch(1)

    def _delete_history_item(self, item: dict):
        ret = QMessageBox.question(
            self, "删除记录",
            f"删除这条下载记录？\n\n{item.get('title','')}\n\n（只删记录，不会删除磁盘上的视频文件）")
        if ret != QMessageBox.Yes:
            return
        self._history = [h for h in self._history if h.get("id") != item.get("id")]
        self._save_history()
        self._refresh_history_list()

    def _clear_history(self):
        if not self._history:
            return
        ret = QMessageBox.question(self, "清空记录", "清空全部下载记录？（不会删除视频文件）")
        if ret != QMessageBox.Yes:
            return
        self._history = []
        self._save_history()
        self._refresh_history_list()

    def _open_history_file(self, item: dict):
        path = item.get("path") or ""
        if path and os.path.isfile(path):
            try:
                os.startfile(path)
                return
            except Exception:
                pass
        folder = os.path.dirname(path) if path else self.config.get("save_dir", "")
        if folder and os.path.isdir(folder):
            try:
                os.startfile(folder)
            except Exception as e:
                QMessageBox.warning(self, "打开失败", str(e))

    def _stop_download(self):
        if self._dl:
            self._dl.cancel()
        self.btn_stop.setEnabled(False)

    def _update_core(self):
        self.btn_update.setEnabled(False)
        self.btn_update.setText("更新中…")
        threading.Thread(
            target=lambda: core.update_ytdlp(self.sig.core_update.emit), daemon=True).start()

    def _on_update_done(self, msg: str):
        self.btn_update.setEnabled(True)
        self.btn_update.setText("  更新核心")
        self._append_log(f"[更新核心] {msg}")

    def _set_ui_state(self, enabled: bool):
        self.url_edit.setEnabled(enabled)
        self.btn_paste.setEnabled(enabled)
        self.btn_download.setEnabled(enabled)
        self.cb_format.setEnabled(enabled)
        self.cb_quality.setEnabled(enabled)
        self.cb_proxy.setEnabled(enabled)
        self.btn_settings.setEnabled(enabled)
        self.btn_update.setEnabled(enabled)
        self.btn_stop.setEnabled(not enabled)
        if not enabled:
            self.tasks_list.setText("正在下载…\n可点击「暂停」停止。")

    def closeEvent(self, event):
        if self._dl is not None:
            self._dl.cancel()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = VideoDownloaderWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        import traceback
        tb = traceback.format_exc()
        _msgbox("程序启动失败", f"发生错误：\n\n{tb}", error=True)
        print(tb)
        raise
