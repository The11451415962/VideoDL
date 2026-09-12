package com.videodl.app.engine

object Platform {
    fun detect(url: String): String = when {
        url.contains("youtube.com", true) || url.contains("youtu.be", true) -> "YouTube"
        url.contains("bilibili.com", true) || url.contains("b23.tv", true) -> "Bilibili"
        url.contains("douyin.com", true) || url.contains("tiktok.com", true) -> "抖音"
        else -> "未知"
    }
}

object ProxyResolver {
    fun resolve(proxyMode: String, proxyUrl: String, url: String): String? = when (proxyMode) {
        "direct" -> null
        "proxy" -> proxyUrl
        else -> if (Platform.detect(url) == "YouTube") proxyUrl else null  // auto
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
     * 兼容性检查 + 转码兜底，见 python/ytdlp_bridge.py）。
     */
    fun resolve(fmt: String, quality: String, platform: String): List<String> {
        if (fmt == "mp3" || quality == "audio") {
            return listOf("-f", "bestaudio/best", "--audio-format", "mp3")
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
