"""bridge for VideoDL Android. Chaquopy loads this from assets."""
import json
from yt_dlp import YoutubeDL

_progress_hook = None
_log_hook = None

def set_hooks(progress_hook, log_hook):
    global _progress_hook, _log_hook
    _progress_hook = progress_hook
    _log_hook = log_hook

def _log(line):
    if _log_hook is not None:
        _log_hook(line)

def on_progress(d):
    if _progress_hook is not None:
        status = d.get("status")
        if status == "downloading":
            pct_raw = d.get("_percent_str", "0%").replace("%", "").strip()
            speed = d.get("_speed_str", "")
            eta = d.get("_eta_str", "")
            _progress_hook(json.dumps({"percent": float(pct_raw), "speed": speed, "eta": eta}))
        elif status == "finished":
            _progress_hook(json.dumps({"percent": 100.0, "speed": "", "eta": ""}))

class _Logger:
    def debug(self, msg):
        if _log_hook is not None and msg:
            _log_hook(msg.replace("\n", " "))
    def warning(self, msg):
        if _log_hook is not None and msg:
            _log_hook(msg.replace("\n", " "))
    def error(self, msg):
        if _log_hook is not None and msg:
            _log_hook(msg.replace("\n", " "))

def _merge_args(opts, args_list):
    i = 0
    while i < len(args_list):
        key = args_list[i]
        if key.startswith("-") and i + 1 < len(args_list) and not args_list[i + 1].startswith("-"):
            opts[key.lstrip("-")] = args_list[i + 1]; i += 2
        else:
            opts[key.lstrip("-")] = True; i += 1

def fetch_info(url, args_list):
    """返回 JSON str：{title, uploader, duration, width, height} 或 {error}。"""
    try:
        opts = {"noplaylist": True, "playlist_items": "1",
                "quiet": True, "no_warnings": True}
        _merge_args(opts, args_list)
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return json.dumps({
                "title": info.get("title", "未知标题"),
                "uploader": info.get("uploader") or info.get("channel", "未知"),
                "duration": info.get("duration", 0),
                "width": info.get("width", 0),
                "height": info.get("height", 0),
            })
    except Exception as e:
        return json.dumps({"error": str(e)})

def download(url, output_path, args_list, ffmpeg_location=""):
    """执行下载，返回 JSON {"ok":true/false,"path":"...","error":"..."}。"""
    try:
        opts = {
            "outtmpl": output_path,
            "noplaylist": True, "playlist_items": "1", "newline": True,
            "progress_hooks": [on_progress],
            "logger": _Logger(),
        }
        if ffmpeg_location:
            opts["ffmpeg_location"] = ffmpeg_location
        _merge_args(opts, args_list)
        with YoutubeDL(opts) as ydl:
            ydl.download([url])
        return json.dumps({"ok": True, "path": output_path})
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)})
