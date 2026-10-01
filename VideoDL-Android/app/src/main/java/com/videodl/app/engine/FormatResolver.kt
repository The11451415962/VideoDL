package com.videodl.app.engine

import com.videodl.app.data.MediaTarget

object Platform {
    fun detect(url: String): String = when {
        url.contains("youtube.com", true) || url.contains("youtu.be", true) -> "YouTube"
        url.contains("bilibili.com", true) || url.contains("b23.tv", true) -> "Bilibili"
        url.contains("douyin.com", true) || url.contains("tiktok.com", true) -> "抖音"
        else -> "未知"
    }
}

/**
 * 代理决策。
 *
 * **纯函数**：只吃事实（有没有 VPN、代理地址通不通），不做探测 —— 探测那步是 IO，
 * 由 [YtdlpEngineImpl.resolveProxy] 负责。
 *
 * 之所以要这样拆：这里原本另有一份"简单版"实现，全项目没人调用；真正跑的是
 * YtdlpEngineImpl 里那一份，而单测测的是没人用的这份，于是两边语义早就漂开了
 * （测试说 auto 只给 YouTube 走代理，实际跑的是"只要地址通，所有站都走代理"）。
 * 现在决策只有一份，测试直接测它。
 */
object ProxyResolver {

    /** [proxyUrl] 为 null 表示直连。[note] 是给用户看的说明（可能为空）。 */
    data class Decision(val proxyUrl: String?, val note: String)

    /**
     * @param platform [Platform.detect] 的结果，auto 模式靠它区分"要不要翻"
     * @param vpnActive 当前是否有 VPN 隧道（有则直连，让隧道自己路由，别套两层）
     * @param proxyReachable 代理地址的端口是否有人监听
     */
    fun resolve(
        proxyMode: String,
        proxyUrl: String,
        platform: String,
        vpnActive: Boolean = false,
        proxyReachable: Boolean = false,
    ): Decision {
        // VPN（tun 模式）自己会路由，再加代理等于绕两层
        if (vpnActive) return Decision(null, "已检测到 VPN，走隧道直连")
        if (proxyMode == "direct") return Decision(null, "")

        val url = proxyUrl.trim()
        if (url.isBlank()) {
            return Decision(
                null,
                if (proxyMode == "proxy") "强制代理但没填地址，已改为直连" else "",
            )
        }

        return when {
            // 强制代理：地址连不上就直连，并且**说明原因**（不静默失败）
            proxyMode == "proxy" && proxyReachable -> Decision(url, "使用代理 $url")
            proxyMode == "proxy" ->
                Decision(null, "代理地址 $url 连不上（代理 App 没开？），本次改为直连")

            // 自动：只给 YouTube 类站点走代理。B 站/抖音走境外节点反而更慢甚至被拒
            proxyReachable && platform == "YouTube" ->
                Decision(url, "自动：代理 $url 可用，YouTube 走代理")

            else -> Decision(null, "")
        }
    }
}

object Format {
    /**
     * 返回 yt-dlp 的 format 参数 key-value 对（顺序相关）。
     *
     * 兼容优先 —— 手机相册 / 剪映(CapCut) 这类 App 只认 H.264 + AAC。
     * 实测 B 站同一个分辨率下同时提供三种编码，yt-dlp 默认按"编码越新越优先"
     * 排序会挑 av01（AV1）：
     *     1080P → avc1 3378k / hvc1 1112k / av01 1074k（默认选中）
     *     720P  → avc1 1556k / hvc1  565k / av01  532k（默认选中）
     * 结果就是"后缀是 .mp4、里面是 AV1"，剪映直接报不支持，用户被迫去在线转码。
     *
     * 所以这里一律优先 avc1 + mp4a，挑不到才逐级放宽（放宽后的编码由下载完成后的
     * 兼容性检查负责报告，见 python/ytdlp_bridge.py）。
     */
    fun resolve(fmt: String, quality: String, platform: String): List<String> {
        if (MediaTarget.isAudio(fmt, quality)) {
            // 音轨优先挑 AAC：源是 AAC 时 --audio-format m4a 走的是 copy（重新封装），
            // 不需要任何编码器；挑到 Opus 就得转码，而精简版 ffmpeg 没有 aac 编码器。
            //
            // 必须 --extract-audio：否则抖音这类只有合并流的站点会把视频直接存成音频后缀，
            // 拖进剪映就「有画面」。bestaudio/xxx 是在没有纯音频流时退回合并流再抽音轨。
            return listOf(
                "-f", "bestaudio/best",
                "--extract-audio",
                "--audio-format", MediaTarget.AUDIO_EXT,
            )
        }

        val height = when (quality) {
            "1080p" -> "[height<=1080]"
            "720p" -> "[height<=720]"
            else -> ""
        }

        if (fmt == "webm") {
            val sel = "bestvideo$height[ext=webm]+bestaudio[ext=webm]/best$height[ext=webm]/best"
            return listOf("-f", sel, "--merge-output-format", "webm")
        }

        // mp4：H.264 + AAC 逐级回退（第一个能被匹配到的优先）
        val sel = listOf(
            "bestvideo$height[vcodec^=avc1]+bestaudio[acodec^=mp4a]",
            "bestvideo$height[vcodec^=avc1]+bestaudio",
            "best[ext=mp4]$height[vcodec^=avc1]",
            "best[ext=mp4]$height",
            "bestvideo$height+bestaudio",
            "best$height",
        ).joinToString("/")
        return listOf("-f", sel, "--merge-output-format", "mp4")
    }
}
