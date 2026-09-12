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
import org.json.JSONArray
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
        // 用户在格式弹窗里挑过具体格式：直接照办（下载视频/仅音频按钮走的也是这条路）
        if (opts.formatSelector.isNotBlank()) {
            val merge = opts.format.ifBlank { "mp4" }
            val args = mutableListOf("-f", opts.formatSelector)
            if (merge != "mp3") args += listOf("--merge-output-format", merge)
            return args
        }
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

    /** 从 http://host:port 取出主机与端口；没有端口时按常见 HTTP 代理端口 7890 处理 */
    private fun proxyHostPort(proxyUrl: String): Pair<String, Int>? = try {
        val u = java.net.URI(if (proxyUrl.contains("://")) proxyUrl else "http://$proxyUrl")
        val host = u.host
        if (host.isNullOrBlank()) null else host to (if (u.port > 0) u.port else 7890)
    } catch (e: Exception) {
        null
    }

    /** 代理端口是否真的有人监听（手机上的 Clash/v2rayNG 一般在本机开端口） */
    private fun proxyReachable(proxyUrl: String): Boolean {
        val hp = proxyHostPort(proxyUrl) ?: return false
        return try {
            java.net.Socket().use { s ->
                s.connect(java.net.InetSocketAddress(hp.first, hp.second), 400)
            }
            true
        } catch (e: Exception) {
            false
        }
    }

    /**
     * 代理决策（Android）。
     *
     * 注意：手机上的代理 App（Clash / v2rayNG 等）通常在本机开一个 HTTP/SOCKS 端口，
     * 所以 **127.0.0.1 是合法地址**，不能像以前那样直接忽略。
     *
     *  - 检测到 VPN 隧道 → 直连（隧道自己会路由，再加代理等于绕两层）
     *  - 强制代理 → 用配置地址；地址连不上就直连并说明原因（不静默失败）
     *  - 自动 → 配了地址且连得上就用，否则直连
     */
    private fun resolveProxy(opts: DownloadOptions, vpnActive: Boolean): Pair<String?, String> {
        if (vpnActive) return null to "已检测到 VPN，走隧道直连"
        if (opts.proxyMode == "direct") return null to ""
        val url = opts.proxyUrl.trim()
        if (url.isBlank()) {
            return null to if (opts.proxyMode == "proxy") "强制代理但没填地址，已改为直连" else ""
        }
        val reachable = proxyReachable(url)
        return when {
            opts.proxyMode == "proxy" && reachable -> url to "使用代理 $url"
            opts.proxyMode == "proxy" ->
                null to "代理地址 $url 连不上（代理 App 没开？），本次改为直连"
            reachable -> url to "自动：代理 $url 可用，走代理"
            else -> null to ""
        }
    }

    /** 把 DownloadOptions 转成 yt-dlp args_list；第二个返回值是给用户看的代理说明 */
    private fun buildArgs(opts: DownloadOptions): Pair<List<String>, String> {
        val args = resolveFormatArgs(opts).toMutableList()
        if (opts.platform == "Bilibili") {
            args += listOf("--add-header", "Referer:https://www.bilibili.com/",
                          "--add-header", "Origin:https://www.bilibili.com")
        }
        val vpnActive = isVpnActive()
        val (proxy, note) = resolveProxy(opts, vpnActive)
        if (proxy != null) args += listOf("--proxy", proxy)
        Log.d(TAG, "buildArgs: vpnActive=$vpnActive proxyMode=${opts.proxyMode} proxy=${proxy ?: "-"} platform=${opts.platform} ffmpeg=${opts.ffmpegLocation}")
        resolveCookieFile(opts)?.let { args += listOf("--cookies", it.absolutePath) }
        args += listOf("--newline", "--no-playlist", "--playlist-items", "1")
        return args to note
    }

    override fun fetchInfo(url: String, options: DownloadOptions): DownloadEvent.Info {
        val (args, proxyNote) = buildArgs(options)
        if (proxyNote.isNotBlank()) Log.d(TAG, "proxy: $proxyNote")
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
            thumbnail = obj.optString("thumbnail", ""),
        )
    }

    override fun fetchDetail(url: String, options: DownloadOptions): MediaDetail {
        val (args, _) = buildArgs(options)
        Log.d(TAG, "fetchDetail: $url")
        val jsonStr = bridge.callAttr("list_formats", url, args.toTypedArray()).toString()
        val obj = JSONObject(jsonStr)
        if (obj.has("error")) throw RuntimeException(obj.getString("error"))
        val arr = obj.optJSONArray("formats") ?: JSONArray()
        val out = ArrayList<FormatOption>(arr.length())
        for (i in 0 until arr.length()) {
            val f = arr.optJSONObject(i) ?: continue
            val height = f.optInt("height", 0)
            val width = f.optInt("width", 0)
            val id = f.optString("id")
            val audioOnly = f.optBoolean("audio_only", false)
            // 竖屏视频（如 1080×1920）要按短边叫法显示，否则会写成 "1920p" 让人误判画质
            val shortSide = when {
                width > 0 && height > 0 -> minOf(width, height)
                height > 0 -> height
                else -> 0
            }
            out += FormatOption(
                id = id,
                label = if (audioOnly) "仅音频" else if (shortSide > 0) "${shortSide}p" else id,
                note = f.optString("note"),
                ext = f.optString("ext"),
                vcodec = f.optString("vcodec"),
                acodec = f.optString("acodec"),
                height = height,
                fps = f.optInt("fps", 0),
                sizeBytes = f.optLong("filesize", 0L),
                tbr = f.optDouble("tbr", 0.0),
                abr = f.optDouble("abr", 0.0),
                audioOnly = audioOnly,
                width = width,
            )
        }
        Log.d(TAG, "fetchDetail -> ${out.size} 个格式")
        return MediaDetail(
            title = obj.optString("title", "未知标题"),
            uploader = obj.optString("uploader", ""),
            duration = obj.optInt("duration", 0),
            thumbnail = obj.optString("thumbnail", ""),
            formats = out,
        )
    }

    override fun download(options: DownloadOptions): Flow<DownloadEvent> = callbackFlow {
        val (args, proxyNote) = buildArgs(options)
        if (proxyNote.isNotBlank()) trySend(DownloadEvent.Log("[提示] $proxyNote"))
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
