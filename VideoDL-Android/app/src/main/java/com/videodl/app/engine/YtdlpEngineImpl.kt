package com.videodl.app.engine

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.util.Log
import com.chaquo.python.Python
import com.videodl.app.data.MediaTarget
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

    /**
     * 解析要用的 cookies.txt。
     *
     * - 设置里选过文件：`SettingsViewModel` 已经把它复制进**私有目录**，
     *   `cookiePathUri` 存的是私有目录里的绝对路径（不是 content://，yt-dlp 才读得了）
     * - 没选到文件：在常见位置自动找一份，省得必须走界面选
     *
     * 顺带把"这次带没带 cookie"写进日志 —— 抖音这类站点完全靠它，
     * 出问题时要能一眼看出是没带 cookie 还是带了没用。
     */
    private fun resolveCookieFile(opts: DownloadOptions): File? {
        if (opts.cookieMode != "file") return null

        val configured = opts.cookiePath.trim()
        if (configured.isNotBlank()) {
            val f = File(configured)
            if (f.isFile && f.length() > 0) {
                Log.d(TAG, "cookies: 用设置里选的 ${f.absolutePath}（${f.length()} 字节）")
                return f
            }
            Log.w(TAG, "cookies: 设置里的路径不可用（$configured），改为自动查找")
        }

        val auto = listOf(
            File(appContext.filesDir, "cookies.txt"),
            File(appContext.getExternalFilesDir(null), "cookies.txt"),
        ).firstOrNull { it.isFile && it.length() > 0 }

        if (auto != null) {
            Log.d(TAG, "cookies: 自动找到 ${auto.absolutePath}（${auto.length()} 字节）")
        } else {
            Log.w(TAG, "cookies: 模式为 file 但没找到任何 cookies.txt，本次不带 cookie")
        }
        return auto
    }

    /** 无 ffmpeg 时不合并/不转码，只下单个带声音的文件（否则会报 ffmpeg not installed） */
    private fun resolveFormatArgs(opts: DownloadOptions): List<String> {
        // 用户在格式弹窗里挑过具体格式：直接照办（下载视频/仅音频按钮走的也是这条路）
        if (opts.formatSelector.isNotBlank()) {
            val args = mutableListOf("-f", opts.formatSelector)
            // 音频产物是单条音轨，没有"合并"这一步，不要传 --merge-output-format
            if (!MediaTarget.isAudio(opts.format, opts.quality)) {
                args += listOf("--merge-output-format", opts.format.ifBlank { "mp4" })
            }
            return args
        }
        val hasFfmpeg = opts.ffmpegLocation.isNotBlank() && File(opts.ffmpegLocation).exists()
        if (hasFfmpeg) {
            return Format.resolve(opts.format, opts.quality, opts.platform)
        }
        return when {
            MediaTarget.isAudio(opts.format, opts.quality) ->
                listOf("-f", "bestaudio[acodec^=mp4a]/bestaudio")
            // 挑不到 avc1 才退而求其次（没有 ffmpeg 就没法合并，只能尽量挑兼容的）
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
     * 代理决策（Android）：这里只负责**探测事实**（有没有 VPN、代理端口通不通），
     * 决策本身交给纯函数 [ProxyResolver.resolve]，这样单测能直接覆盖真正生效的规则。
     *
     * 注意：手机上的代理 App（Clash / v2rayNG 等）通常在本机开一个 HTTP/SOCKS 端口，
     * 所以 **127.0.0.1 是合法地址**，不能像以前那样直接忽略。
     */
    private fun resolveProxy(opts: DownloadOptions, vpnActive: Boolean): Pair<String?, String> {
        val url = opts.proxyUrl.trim()
        // 只在真正需要判断"通不通"时才去连端口，省掉一次无谓的连接尝试
        val needProbe = !vpnActive && opts.proxyMode != "direct" && url.isNotBlank()
        val reachable = needProbe && proxyReachable(url)
        val d = ProxyResolver.resolve(
            proxyMode = opts.proxyMode,
            proxyUrl = url,
            platform = opts.platform,
            vpnActive = vpnActive,
            proxyReachable = reachable,
        )
        return d.proxyUrl to d.note
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
                    send(DownloadEvent.Cancelled)
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
