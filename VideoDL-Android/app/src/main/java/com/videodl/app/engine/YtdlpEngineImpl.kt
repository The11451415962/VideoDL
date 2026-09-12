package com.videodl.app.engine

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.util.Log
import com.chaquo.python.Python
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.withContext
import org.json.JSONObject

class YtdlpEngineImpl(context: Context) : YtdlpEngine {

    private val TAG = "VideoDL"
    private val appContext = context.applicationContext
    private val py: Python = Python.getInstance()
    private val bridge = py.getModule("ytdlp_bridge")
    @Volatile private var cancelled = false

    /** 检测当前是否有 VPN 隧道（tun 模式），有则直连，让 VPN 自动路由 */
    private fun isVpnActive(): Boolean {
        return try {
            val cm = appContext.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
            val vpn = cm.allNetworks.any { n ->
                cm.getNetworkCapabilities(n)?.hasTransport(NetworkCapabilities.TRANSPORT_VPN) == true
            }
            Log.d(TAG, "isVpnActive=$vpn")
            vpn
        } catch (e: Exception) {
            Log.e(TAG, "isVpnActive error", e)
            false
        }
    }

    /** 解析要用的 Cookie 文件：优先配置的 file 路径，其次 App 目录下自动检测的 cookies.txt */
    private fun resolveCookieFile(opts: DownloadOptions): File? {
        if (opts.cookieMode == "file" && opts.cookiePath.isNotBlank()) {
            val f = File(opts.cookiePath)
            if (f.exists()) return f
        }
        val auto = File(appContext.getExternalFilesDir(null), "cookies.txt")
        return if (auto.exists()) auto else null
    }

    /** 无 ffmpeg 时不合并/不转码，只下单个带声音的文件（否则会报 ffmpeg not installed） */
    private fun resolveFormatArgs(opts: DownloadOptions): List<String> {
        val hasFfmpeg = opts.ffmpegLocation.isNotBlank() && File(opts.ffmpegLocation).exists()
        if (hasFfmpeg) {
            return Format.resolve(opts.format, opts.quality, opts.platform)
        }
        return when {
            opts.quality == "audio" || opts.format == "mp3" -> listOf("-f", "bestaudio/best")
            // 挑不到 avc1 才退而求其次（没有 ffmpeg 就没法转码，只能尽量挑兼容的）
            else -> listOf(
                "-f",
                "b[ext=${opts.format}][vcodec^=avc1]/b[ext=${opts.format}]/b",
            )
        }
    }

    /** 把 DownloadOptions 转成 yt-dlp args_list（复用 Task 3 已翻译的 Format / Proxy / Platform） */
    private fun buildArgs(opts: DownloadOptions): List<String> {
        val args = resolveFormatArgs(opts).toMutableList()
        if (opts.platform == "Bilibili") {
            args += listOf("--add-header", "Referer:https://www.bilibili.com/",
                          "--add-header", "Origin:https://www.bilibili.com")
        }
        // 代理策略（Android 版）：
        // - VPN 开启 → 直连（隧道自动路由）
        // - 强制代理(proxy) 且地址不是本机 → 用该地址
        // - 其余(auto/direct) → 直连（手机上 VPN 是透明的；127.0.0.1 是桌面端默认值，在手机上是无效的）
        val vpnActive = isVpnActive()
        if (!vpnActive && opts.proxyMode == "proxy") {
            val p = opts.proxyUrl
            if (p.isNotBlank() && !p.contains("127.0.0.1") && !p.contains("localhost")) {
                args += listOf("--proxy", p)
            }
        }
        Log.d(TAG, "buildArgs: vpnActive=$vpnActive proxyMode=${opts.proxyMode} platform=${opts.platform} ffmpeg=${opts.ffmpegLocation}")
        resolveCookieFile(opts)?.let { args += listOf("--cookies", it.absolutePath) }
        args += listOf("--newline", "--no-playlist", "--playlist-items", "1")
        return args
    }

    override fun fetchInfo(url: String, options: DownloadOptions): DownloadEvent.Info {
        val args = buildArgs(options)
        Log.d(TAG, "fetchInfo: $url")
        val jsonStr = bridge.callAttr("fetch_info", url, args.toTypedArray()).toString()
        Log.d(TAG, "fetchInfo result: $jsonStr")
        val obj = JSONObject(jsonStr)
        if (obj.has("error")) {
            val err = obj.getString("error")
            Log.e(TAG, "fetchInfo error: $err")
            throw RuntimeException(err)
        }
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
                Log.d(TAG, "download: ${options.url} -> ${options.outputPath}")
                val resultStr = bridge.callAttr(
                    "download", options.url, options.outputPath, args.toTypedArray(), options.ffmpegLocation
                ).toString()
                Log.d(TAG, "download result: $resultStr")
                val res = JSONObject(resultStr)
                val err = res.optString("error", "")
                if (cancelled || err == "__CANCELLED__") {
                    send(DownloadEvent.Error("用户取消"))
                } else if (res.getBoolean("ok")) {
                    send(DownloadEvent.Finished(res.getString("path")))
                } else {
                    Log.e(TAG, "download error: $err")
                    send(DownloadEvent.Error(err.ifBlank { "下载失败" }))
                }
            } catch (e: Exception) {
                Log.e(TAG, "download exception", e)
                send(DownloadEvent.Error(e.message ?: "未知错误"))
            }
            close()
        }
        awaitClose { cancelled = true }
    }

    override fun cancel() {
        cancelled = true
        try { bridge.callAttr("cancel") } catch (_: Exception) {}
    }
}
