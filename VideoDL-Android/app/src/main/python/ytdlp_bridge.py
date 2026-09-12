"""bridge for VideoDL Android. Chaquopy loads this from assets."""
import json
from yt_dlp import YoutubeDL

_progress_hook = None
_log_hook = None
_cancel_flag = False


def set_hooks(progress_hook, log_hook):
    global _progress_hook, _log_hook
    _progress_hook = progress_hook
    _log_hook = log_hook


def cancel():
    """请求取消当前下载（在 progress hook 中生效）。"""
    global _cancel_flag
    _cancel_flag = True


def _log(line):
    if _log_hook is not None:
        _log_hook(line)


def on_progress(d):
    global _cancel_flag
    if _cancel_flag:
        # KeyboardInterrupt 是 BaseException，不会被 yt-dlp 的 except Exception 吞掉
        raise KeyboardInterrupt
    if _progress_hook is not None:
        status = d.get("status")
        if status == "downloading":
            pct_raw = d.get("_percent_str", "0%").replace("%", "").strip()
            try:
                pct = float(pct_raw)
            except ValueError:
                pct = 0.0
            _progress_hook(json.dumps({
                "percent": pct,
                "speed": d.get("_speed_str", ""),
                "eta": d.get("_eta_str", ""),
            }))
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


# CLI 风格参数名 → yt-dlp Python API 参数名。
# 之前直接把 "-f" 之类的键塞进 opts，yt-dlp 会静默忽略，导致格式/画质/mp3/Referer/Cookie 全部失效。
_CLI_TO_API = {
    "f": "format",
    "audio-format": "audioformat",
    "merge-output-format": "merge_output_format",
    "cookies": "cookiefile",
    "proxy": "proxy",
    "newline": "newline",
    "no-playlist": "noplaylist",
    "playlist-items": "playlist_items",
}


def _merge_args(opts, args_list):
    i = 0
    while i < len(args_list):
        raw = args_list[i]
        key = raw.lstrip("-")

        # --add-header "Key: Value" 需要合并成 dict，且多条要累加
        if key == "add-header":
            if i + 1 < len(args_list) and ":" in args_list[i + 1]:
                name, _, value = args_list[i + 1].partition(":")
                opts.setdefault("add_headers", {})[name.strip()] = value.strip()
                i += 2
            else:
                i += 1
            continue

        api_key = _CLI_TO_API.get(key, key)
        # 布尔开关：后面没有值，或下一个又是 "-" 开头
        if i + 1 >= len(args_list) or args_list[i + 1].startswith("-"):
            opts[api_key] = True
            i += 1
        else:
            opts[api_key] = args_list[i + 1]
            i += 2


def fetch_info(url, args_list):
    """返回 JSON str：{title, uploader, duration, width, height} 或 {error}。"""
    try:
        args_list = list(args_list)  # Chaquopy 传入 Java ArrayList，转成 Python list
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
    global _cancel_flag
    _cancel_flag = False
    try:
        args_list = list(args_list)  # Chaquopy 传入 Java ArrayList，转成 Python list
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
    except KeyboardInterrupt:
        return json.dumps({"ok": False, "error": "__CANCELLED__"})
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)})
