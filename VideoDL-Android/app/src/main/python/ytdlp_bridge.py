"""bridge for VideoDL Android. Chaquopy loads this from assets."""
import json
import os
import re
import subprocess
from yt_dlp import YoutubeDL

_progress_hook = None
_log_hook = None
_cancel_flag = False

# ffmpeg 路径 -> 可用编码器名字集合（探测一次就够，别每次转码都问一遍）
_encoder_cache = {}


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
                "width": f.get("width") or 0,
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
             "stream=codec_type,codec_name,disposition:format=duration",
             "-of", "json", path],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=60)
        data = json.loads(out.stdout.decode("utf-8", "replace") or "{}")
        v = a = None
        for st in data.get("streams", []):
            disposition = st.get("disposition") or {}
            if disposition.get("attached_pic"):
                continue
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


def _has_color_info(ffprobe, path):
    """视频流有没有色彩描述。返回 True/False；探测不出来返回 None（未知）。"""
    try:
        out = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries",
             "stream=codec_type,color_primaries,color_transfer,color_space",
             "-of", "json", path],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=60)
        data = json.loads(out.stdout.decode("utf-8", "replace") or "{}")
        for st in data.get("streams", []):
            if st.get("codec_type") == "video":
                return all(st.get(k) not in (None, "", "unknown")
                           for k in ("color_primaries", "color_transfer", "color_space"))
        return None
    except Exception:
        return None


def _run_copy_remux(ffmpeg_location, path, tmp):
    """`-c copy` 重封装并补上色彩参数，返回 (returncode, 尾部输出)。

    注意是 `-c copy`：不重新编码，所以**没有编码器的精简 ffmpeg 也能跑**
    （实测 25 秒视频只多 19~35 字节）。
    """
    cmd = [ffmpeg_location, "-y", "-hide_banner", "-loglevel", "error",
           "-i", path,
           "-c", "copy",
           "-color_primaries", "bt709", "-color_trc", "bt709",
           "-colorspace", "bt709", "-color_range", "tv",
           "-movflags", "+faststart", tmp]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
    except Exception as e:
        return 127, [f"无法启动 ffmpeg: {e}"]
    tail = []
    try:
        for raw in iter(proc.stdout.readline, b""):
            line = raw.decode("utf-8", "replace").strip()
            if line:
                tail.append(line)
                del tail[:-4]
        proc.wait(timeout=300)
    except Exception as e:
        tail.append(f"重封装异常: {e}")
    finally:
        try:
            proc.stdout.close()
        except Exception:
            pass
    return proc.returncode, tail


def _ensure_color_metadata(path, ffmpeg_location):
    """给 MP4 补上色彩描述（容器里的 `colr` box + SPS 里的 VUI 色彩）。

    **为什么必须做**：真机实测（2026-09-13）—— YouTube 的原始 H.264 流被 `-c copy`
    原样封装进来的 MP4，在手机相册和剪映里**能播，但一点「编辑」就报「格式不支持」**；
    而同一段视频**重新编码**过的（ffmpeg/libx264 会自动写 colr + pasp）就能正常编辑。

    对照实验（同一段视频，转过格式 vs 没转）：

        avc1 采样描述:  avcC  btrt                     ← 编辑不了
        avc1 采样描述:  avcC  colr(19B)  pasp(16B)  btrt ← 能编辑

    其余（编码/profile/level/分辨率/帧率/像素格式/音频参数/容器品牌）**完全相同**。
    媒体库里也印证了同一点：缺色彩信息的文件 color_range/standard/transfer 都是 NULL。
    结论：编辑器建立色彩管线需要这个信息，没有就拒。

    **怎么补**：`-c copy` 重封装一次并指定色彩参数即可，**不需要重新编码**，
    手机上那个没有编码器的精简 ffmpeg 也能跑（已实测，输出 colr 与能编辑的文件字节相同）。

    探测不出来（None）就什么都不做 —— 宁可不动，也不要瞎改用户的文件。
    失败也不影响下载：保留原文件，顶多还是编辑不了。
    """
    if not ffmpeg_location or not os.path.isfile(ffmpeg_location):
        return
    if not path.lower().endswith(".mp4"):
        return                                   # colr 是 mp4 的概念，mkv/webm 不适用
    if _has_color_info(_ffprobe_path(ffmpeg_location), path) is not False:
        return                                   # 已有色彩信息，或未知 → 不动

    tmp = path + ".colr.mp4"
    rc, tail = _run_copy_remux(ffmpeg_location, path, tmp)
    if rc == 0 and os.path.isfile(tmp) and os.path.getsize(tmp) > 0:
        try:
            os.replace(tmp, path)
            _log("[提示] 已补上色彩信息（相册 / 剪映才能「编辑」这个视频）")
        except Exception as e:
            _log(f"[警告] 色彩信息写入失败：{e}")
    else:
        _log(f"[警告] 补色彩信息失败，保留原文件：{' | '.join(tail)[:160]}")
    try:
        if os.path.isfile(tmp):
            os.remove(tmp)
    except Exception:
        pass


def remux_two_inputs(video_only, original, out, ffmpeg_location):
    """把「重新编码过的视频轨」和「原始音频轨」合成一个 mp4。

    两条流都是 `-c copy` 纯搬运，**不重新编码**，所以打包的精简 ffmpeg（没有编码器）
    也能跑。顺带补上 `colr` 色彩描述和 faststart。

    `-map 1:a:0?` 末尾的问号让音频轨可选：源文件没有音频时照样能合成。

    返回 JSON 字符串 {"ok":true} 或 {"ok":false,"error":"..."}（与其他桥函数一致）。
    """
    if not ffmpeg_location or not os.path.isfile(ffmpeg_location):
        return json.dumps({"ok": False, "error": "没有可用的 ffmpeg"})
    cmd = [ffmpeg_location, "-y", "-hide_banner", "-loglevel", "error",
           "-i", video_only, "-i", original,
           "-map", "0:v:0", "-map", "1:a:0?",
           "-c", "copy",
           "-color_primaries", "bt709", "-color_trc", "bt709",
           "-colorspace", "bt709", "-color_range", "tv",
           "-movflags", "+faststart", out]
    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, timeout=900)
    except Exception as e:
        return json.dumps({"ok": False, "error": f"无法启动 ffmpeg: {e}"})
    if proc.returncode == 0 and os.path.isfile(out) and os.path.getsize(out) > 0:
        return json.dumps({"ok": True})
    tail = proc.stdout.decode("utf-8", "replace").strip().splitlines()[-3:]
    return json.dumps({"ok": False, "error": " | ".join(tail)
                       or f"ffmpeg 退出码 {proc.returncode}"})


def _final_path(info, output_path):
    """合并后的真实文件路径（yt-dlp 有时会改容器导致扩展名变化）。"""
    try:
        rd = (info or {}).get("requested_downloads") or []
        if rd and rd[0].get("filepath"):
            return rd[0]["filepath"]
    except Exception:
        pass
    return output_path


def _available_encoders(ffmpeg_location):
    """探测这个 ffmpeg 支持哪些编码器，只探一次并缓存。

    打包进 APK 的是 LGPL 精简包，`--disable-everything` 之后只编了 mjpeg ——
    **没有 libx264，也没有 aac**。不先探一下就盲目跑两次转码，既浪费时间，
    又只会打出一句"转码失败（crf + 进度）"，把"这个二进制根本不能编码"
    误报成"参数不对"，让人以为是重试能解决的临时问题。

    探测失败时返回空集合，调用方应当退回到"照旧试一次"的行为。
    """
    if ffmpeg_location in _encoder_cache:
        return _encoder_cache[ffmpeg_location]
    found = set()
    try:
        out = subprocess.run(
            [ffmpeg_location, "-hide_banner", "-encoders"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20,
        ).stdout.decode("utf-8", "replace")
        # 形如 " V....D libx264   libx264 H.264 ..." / " A....D aac   AAC ..."
        for line in out.splitlines():
            m = re.match(r"\s*[VAS]\S*\s+(\S+)", line)
            if m:
                found.add(m.group(1))
    except Exception as e:
        _log(f"[警告] 无法探测 ffmpeg 编码器：{e}")
    _encoder_cache[ffmpeg_location] = found
    return found


def _run_transcode(ffmpeg_location, path, tmp, extra, total,
                   venc="libx264", aenc="aac"):
    """跑一次 ffmpeg 转码，返回 (returncode, 尾部输出)。

    边跑边把进度回传给进度条；用户取消时立刻杀掉进程。
    编码器由调用方探测后传进来（不同构建支持的不一样）。
    """
    global _cancel_flag
    cmd = [ffmpeg_location, "-y", "-hide_banner", "-loglevel", "error",
           "-i", path,
           "-c:v", venc]
    # -preset 是 x264/x265 特有的，openh264 / mediacodec 不认，会直接报参数错
    if venc in ("libx264", "libx265"):
        cmd += ["-preset", "veryfast"]
    cmd += [
           # 只限制"超过 1080P"的情况：4K 用手机软件编码会慢到无法接受
           "-vf", "scale=-2:'min(1080,ih)'",
           "-pix_fmt", "yuv420p",
           "-c:a", aenc, "-b:a", "192k",
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

    ⚠️ 已知问题：**当前打包进 APK 的 ffmpeg 一个 H.264 编码器都没有**，所以这个转码
    在真机上不会成功。打包的 libffmpeg.so 是按
    `--disable-gpl --enable-version3 --disable-everything` 构建的 LGPL 精简包，
    只编了 `mjpeg` 一个编码器 —— 没有 libx264、没有 h264、也没有 aac。

    这不是忘了接线，是许可证约束的必然结果：libx264 是 GPL，所以任何能闭源
    商用的 ffmpeg 构建都不含它。要让转码真的可用，得重建 libffmpeg.so，
    改用 `--enable-libopenh264`（BSD）或
    `--enable-jni --enable-mediacodec --enable-encoder=h264_mediacodec`（Apache-2.0，
    手机硬件编码，更快），另加原生 aac 编码器。详见 README「已知问题」。

    所以这里改成**先探测编码器能力再决定**：探测到没有 H.264 编码器就立刻如实说明并
    放弃，不再白跑两次 ffmpeg、也不再打出"参数不对"这种误导人的日志。
    等 ffmpeg 重建好之后，这个函数不用改就能自动用上新编码器。

    （合并音视频流不受影响：那条路走 -c copy，不需要编码器。）

    返回 (ok, reason)；reason == "cancelled" 表示用户中断。
    """
    global _cancel_flag
    if not os.path.isfile(path):
        return True, ""
    # 音频产物绝不能走「转成 H.264 视频」——否则会变成内容是 MP4、后缀还是音频的怪文件
    if os.path.splitext(path)[1].lower() in {
        ".mp3", ".m4a", ".aac", ".opus", ".ogg", ".wav", ".flac", ".wma",
    }:
        _log("[信息] 音频文件，跳过视频兼容性转码")
        return True, ""

    vcodec, acodec, probed_dur = _probe(_ffprobe_path(ffmpeg_location), path)
    if vcodec is None:
        _log("[信息] 无视频轨（或仅有封面图），跳过视频兼容性转码")
        return True, ""
    if vcodec == "h264" and acodec in ("aac", None, ""):
        return True, ""
    if not ffmpeg_location or not os.path.isfile(ffmpeg_location):
        _log(f"[警告] 视频编码是 {vcodec}/{acodec}，剪映等 App 可能不支持；"
             f"未找到 ffmpeg，无法自动转码")
        return False, f"codec={vcodec}/{acodec}"

    total = duration or probed_dur or 0
    tmp = path + ".compat.mp4"

    # 先问清楚这个 ffmpeg 会什么再动手。打包的精简包一个 H.264 编码器都没有，
    # 盲目跑两次只会浪费时间，还会把"这二进制根本不能编码"报成"参数不对"。
    encoders = _available_encoders(ffmpeg_location)
    venc = next((e for e in ("libx264", "libopenh264", "h264_mediacodec", "h264")
                 if e in encoders), "libx264")
    if encoders and venc not in encoders:
        _log(f"[警告] 这个 ffmpeg 没有 H.264 编码器，转不了码；已保留原文件"
             f"（{vcodec}/{acodec}，剪映/相册可能打不开）。"
             f"建议在格式弹窗里改选标着 H.264 的清晰度重下。")
        return False, f"no-h264-encoder({vcodec}/{acodec})"
    aenc = "aac" if (not encoders or "aac" in encoders) else "copy"

    _log(f"[提示] 视频编码是 {vcodec}（剪映不支持），正在用 {venc} 转成 H.264 + "
         f"{'AAC' if aenc == 'aac' else '原音轨'}…")

    # 第一次：质量优先（crf）+ 实时进度；失败则降级为固定码率、不带进度协议。
    # crf 只有 x264/x265 认，openh264 / mediacodec 传了会直接报参数错，所以按编码器决定。
    attempts = []
    if venc in ("libx264", "libx265"):
        attempts.append((["-crf", "20", "-progress", "pipe:1", "-nostats"], "crf + 进度"))
    attempts.append((["-b:v", "4000k"], "固定码率"))
    for extra, desc in attempts:
        if _cancel_flag:
            return False, "cancelled"
        if os.path.isfile(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass
        rc, tail = _run_transcode(ffmpeg_location, path, tmp, extra, total, venc, aenc)
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

    _log("[警告] 转码没有成功，已保留原文件；可改用较低清晰度重下（1080P 一般是 H.264）")
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
        ok, reason = _ensure_importable(final_path, ffmpeg_location, duration)
        if reason == "cancelled":
            return json.dumps({"ok": False, "error": "__CANCELLED__"})
        # 补色彩描述（-c copy，不重编码）：缺了它，相册/剪映里能播但一点「编辑」就报
        # 「格式不支持」。放在转码之后，保证最终落盘的文件一定带上。
        if not _cancel_flag:
            _ensure_color_metadata(final_path, ffmpeg_location)
        if not os.path.isfile(final_path):
            return json.dumps({"ok": False, "error": "下载结束但找不到输出文件：" + final_path})
        if not ok:
            return json.dumps({
                "ok": True, "path": final_path,
                "warning": "编码不兼容，剪映/相册可能无法打开",
            })
        return json.dumps({"ok": True, "path": final_path})
    except KeyboardInterrupt:
        return json.dumps({"ok": False, "error": "__CANCELLED__"})
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)})
