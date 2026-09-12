"""bridge for VideoDL Android. Chaquopy loads this from assets."""
import json
import os
import subprocess
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
    """返回 JSON str：{title, uploader, duration, width, height, thumbnail} 或 {error}。"""
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
                "thumbnail": info.get("thumbnail") or "",
            })
    except Exception as e:
        return json.dumps({"error": str(e)})


def list_formats(url, args_list):
    """列出这个视频可选的所有格式（给"格式选择"底部弹窗用）。

    返回 JSON：{"title":..., "thumbnail":..., "duration":..., "uploader":...,
                "formats":[{id,note,ext,vcodec,acodec,height,fps,filesize,tbr,abr,audio_only}]}
    或 {"error": "..."}
    """
    try:
        args_list = list(args_list)
        opts = {"noplaylist": True, "playlist_items": "1",
                "quiet": True, "no_warnings": True}
        _merge_args(opts, args_list)
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        formats = []
        for f in (info.get("formats") or []):
            vcodec = (f.get("vcodec") or "none")
            acodec = (f.get("acodec") or "none")
            formats.append({
                "id": f.get("format_id") or "",
                "note": f.get("format_note") or "",
                "ext": f.get("ext") or "",
                "vcodec": vcodec,
                "acodec": acodec,
                "height": f.get("height") or 0,
                "fps": f.get("fps") or 0,
                "filesize": f.get("filesize") or f.get("filesize_approx") or 0,
                "tbr": f.get("tbr") or 0,
                "abr": f.get("abr") or 0,
                "audio_only": vcodec == "none" and acodec != "none",
            })
        return json.dumps({
            "title": info.get("title", "未知标题"),
            "uploader": info.get("uploader") or info.get("channel", ""),
            "duration": info.get("duration") or 0,
            "thumbnail": info.get("thumbnail") or "",
            "formats": formats,
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


def _ffprobe_path(ffmpeg_location):
    """推导 ffprobe 路径。

    安卓上 ffprobe 与 ffmpeg 一起躺在 nativeLibraryDir 里（libffprobe.so）；
    主机上则是同目录的 ffprobe(.exe) —— 两种都认，方便在电脑上直接验证这段代码。
    """
    if not ffmpeg_location:
        return ""
    d = os.path.dirname(ffmpeg_location)
    base = os.path.basename(ffmpeg_location)
    cands = []
    if base.endswith(".so"):
        cands.append(os.path.join(d, base.replace("ffmpeg", "ffprobe")))
    cands += [
        os.path.join(d, "ffprobe.exe"),
        os.path.join(d, "ffprobe"),
        os.path.join(d, base.replace("ffmpeg", "ffprobe")),
    ]
    for p in cands:
        if p and os.path.isfile(p):
            return p
    return ""


def _probe(ffprobe, path):
    """返回 (vcodec, acodec, duration_seconds)；失败返回 (None, None, 0)。"""
    try:
        out = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries",
             "stream=codec_type,codec_name:format=duration",
             "-of", "json", path],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=60)
        data = json.loads(out.stdout.decode("utf-8", "replace") or "{}")
        v = a = None
        for st in data.get("streams", []):
            if st.get("codec_type") == "video" and v is None:
                v = (st.get("codec_name") or "").lower()
            elif st.get("codec_type") == "audio" and a is None:
                a = (st.get("codec_name") or "").lower()
        dur = 0.0
        try:
            dur = float(data.get("format", {}).get("duration") or 0)
        except (TypeError, ValueError):
            dur = 0.0
        return v, a, dur
    except Exception:
        return None, None, 0


def _final_path(info, output_path):
    """合并后的真实文件路径（yt-dlp 有时会改容器导致扩展名变化）。"""
    try:
        rd = (info or {}).get("requested_downloads") or []
        if rd and rd[0].get("filepath"):
            return rd[0]["filepath"]
    except Exception:
        pass
    return output_path


def _run_transcode(ffmpeg_location, path, tmp, extra, total):
    """跑一次 ffmpeg 转码，返回 (returncode, 尾部输出)。

    边跑边把进度回传给进度条；用户取消时立刻杀掉进程。
    """
    global _cancel_flag
    cmd = [ffmpeg_location, "-y", "-hide_banner", "-loglevel", "error",
           "-i", path,
           "-c:v", "libx264", "-preset", "veryfast",
           # 只限制"超过 1080P"的情况：4K 用手机软件编码会慢到无法接受
           "-vf", "scale=-2:'min(1080,ih)'",
           "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k",
           "-movflags", "+faststart"] + extra + [tmp]

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
    except Exception as e:
        return 127, [f"无法启动 ffmpeg: {e}"]

    tail = []
    try:
        for raw in iter(proc.stdout.readline, b""):
            if _cancel_flag:
                try:
                    proc.kill()
                except Exception:
                    pass
                return -1, ["cancelled"]
            line = raw.decode("utf-8", "replace").strip()
            if line.startswith("out_time_ms=") and total > 0:
                try:
                    done_s = int(line.split("=", 1)[1]) / 1000000.0
                    pct = max(0.0, min(99.0, done_s / total * 100.0))
                    if _progress_hook is not None:
                        _progress_hook(json.dumps(
                            {"percent": pct, "speed": "", "eta": "转码中"}))
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
        tail.append(f"转码过程异常: {e}")
    finally:
        try:
            proc.stdout.close()
        except Exception:
            pass
    return proc.returncode, tail


def _ensure_importable(path, ffmpeg_location, duration=0):
    """确保产出文件能被手机相册 / 剪映直接导入（H.264 + AAC + faststart）。

    格式选择已经优先挑 avc1/mp4a 了，但有些清晰度只提供 HEVC/AV1（例如 B 站
    1080P+ / 4K）。这时把它命名成 .mp4 是骗人的 —— 用打包进来的 ffmpeg
    真转一遍，用户就不用再去在线转码平台。

    打包的精简 ffmpeg 未必支持全部选项（实测它连 crf 选项都没有），
    所以先试完整参数，失败再降级重试一次。

    返回 (ok, reason)；reason == "cancelled" 表示用户中断。
    """
    global _cancel_flag
    if not os.path.isfile(path):
        return True, ""

    vcodec, acodec, probed_dur = _probe(_ffprobe_path(ffmpeg_location), path)
    if vcodec is None:
        _log("[提示] 读不到编码信息，跳过兼容性检查")
        return True, ""
    if vcodec == "h264" and acodec in ("aac", None, ""):
        return True, ""
    if not ffmpeg_location or not os.path.isfile(ffmpeg_location):
        _log(f"[警告] 视频编码是 {vcodec}/{acodec}，剪映等 App 可能不支持；"
             f"未找到 ffmpeg，无法自动转码")
        return False, f"codec={vcodec}/{acodec}"

    total = duration or probed_dur or 0
    _log(f"[提示] 视频编码是 {vcodec}（剪映不支持），正在转成 H.264 + AAC…")
    tmp = path + ".compat.mp4"

    # 第一次：质量优先（crf）+ 实时进度；失败则降级为固定码率、不带进度协议
    attempts = [
        (["-crf", "20", "-progress", "pipe:1", "-nostats"], "crf + 进度"),
        (["-b:v", "4000k"], "固定码率降级"),
    ]
    for extra, desc in attempts:
        if _cancel_flag:
            return False, "cancelled"
        if os.path.isfile(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass
        rc, tail = _run_transcode(ffmpeg_location, path, tmp, extra, total)
        if rc == -1:
            _log("[提示] 已取消转码")
            return False, "cancelled"
        if rc == 0 and os.path.isfile(tmp):
            try:
                os.replace(tmp, path)
            except Exception as e:
                _log(f"[警告] 转码结果写入失败：{e}")
                return False, str(e)
            _log("[完成] 已转成 H.264 + AAC，手机相册 / 剪映可直接导入")
            return True, ""
        _log(f"[警告] 转码失败（{desc}）：{' | '.join(tail)[:200]}")

    _log("[警告] 两种参数都失败，已保留原文件；可直接用较低清晰度重下（1080P 一般是 H.264）")
    return False, "transcode-failed"


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
            # 用 extract_info(download=True) 而不是 download()，为了拿到合并后
            # 的真实文件路径和时长（转码进度要用）
            info = ydl.extract_info(url, download=True)
        if _cancel_flag:
            return json.dumps({"ok": False, "error": "__CANCELLED__"})
        final_path = _final_path(info, output_path)
        try:
            duration = int((info or {}).get("duration") or 0)
        except (TypeError, ValueError):
            duration = 0
        _, reason = _ensure_importable(final_path, ffmpeg_location, duration)
        if reason == "cancelled":
            return json.dumps({"ok": False, "error": "__CANCELLED__"})
        if not os.path.isfile(final_path):
            return json.dumps({"ok": False, "error": "下载结束但找不到输出文件：" + final_path})
        return json.dumps({"ok": True, "path": final_path})
    except KeyboardInterrupt:
        return json.dumps({"ok": False, "error": "__CANCELLED__"})
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)})
