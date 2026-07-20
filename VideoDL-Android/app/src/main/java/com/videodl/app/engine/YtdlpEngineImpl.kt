package com.videodl.app.engine

import com.chaquo.python.Python
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.withContext
import org.json.JSONObject

class YtdlpEngineImpl : YtdlpEngine {

    private val py: Python = Python.getInstance()
    private val bridge = py.getModule("ytdlp_bridge")
    @Volatile private var cancelled = false

    /** 把 DownloadOptions 转成 yt-dlp args_list（复用 Task 3 已翻译的 Format / Proxy / Platform） */
    private fun buildArgs(opts: DownloadOptions): List<String> {
        val args = Format.resolve(opts.format, opts.quality, opts.platform).toMutableList()
        if (opts.platform == "Bilibili") {
            args += listOf("--add-header", "Referer:https://www.bilibili.com/",
                          "--add-header", "Origin:https://www.bilibili.com")
        }
        ProxyResolver.resolve(opts.proxyMode, opts.proxyUrl, opts.url)?.let {
            args += listOf("--proxy", it)
        }
        if (opts.cookieMode == "file" && opts.cookiePath.isNotBlank()) {
            args += listOf("--cookies", opts.cookiePath)
        }
        args += listOf("--newline", "--no-playlist", "--playlist-items", "1")
        return args
    }

    override fun fetchInfo(url: String, options: DownloadOptions): DownloadEvent.Info {
        val args = buildArgs(options)
        val jsonStr = bridge.callAttr("fetch_info", url, args).toString()
        val obj = JSONObject(jsonStr)
        if (obj.has("error")) throw RuntimeException(obj.getString("error"))
        val w = obj.optInt("width", 0); val h = obj.optInt("height", 0)
        return DownloadEvent.Info(
            title = obj.optString("title", "未知标题"),
            uploader = obj.optString("uploader", "未知"),
            duration = obj.optInt("duration", 0),
            resolution = if (w > 0) "${w}x${h}" else "?",
        )
    }

    override fun download(options: DownloadOptions): Flow<DownloadEvent> = callbackFlow {
        val args = buildArgs(options)
        cancelled = false
        // 注册 Kotlin→Python 回调（字符串 JSON 回调,见 Task 5 bridge）
        bridge.callAttr("set_hooks",
            com.chaquo.python.PyObject.fromJava { line: String ->
                trySend(DownloadEvent.Log(line)); true
            },
            com.chaquo.python.PyObject.fromJava { jsonLine: String ->
                try {
                    val o = JSONObject(jsonLine)
                    val pct = o.optDouble("percent", 0.0).toFloat()
                    val speed = o.optString("speed", "")
                    val eta = o.optString("eta", "")
                    trySend(DownloadEvent.Progress(pct, speed, eta))
                } catch (_: Exception) {}
                true
            }
        )
        withContext(Dispatchers.IO) {
            try {
                send(DownloadEvent.Started)
                val resultStr = bridge.callAttr(
                    "download", options.url, options.outputPath, args, options.ffmpegLocation
                ).toString()
                val res = JSONObject(resultStr)
                if (cancelled) {
                    send(DownloadEvent.Error("用户取消"))
                } else if (res.getBoolean("ok")) {
                    send(DownloadEvent.Finished(res.getString("path")))
                } else {
                    send(DownloadEvent.Error(res.optString("error", "下载失败")))
                }
            } catch (e: Exception) {
                send(DownloadEvent.Error(e.message ?: "未知错误"))
            }
            close()
        }
        awaitClose { cancelled = true }
    }

    override fun cancel() { cancelled = true }
}
