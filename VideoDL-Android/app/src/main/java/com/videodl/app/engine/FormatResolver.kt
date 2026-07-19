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
     * 返回 yt-dlp 的 format 参数 key-value 对（顺序相关），
     * 与桌面版 resolve_format_string 一一对应。platform = Platform.detect(url)。
     */
    fun resolve(fmt: String, quality: String, platform: String): List<String> {
        if (fmt == "mp3" || quality == "audio") {
            return listOf("-f", "bestaudio/best", "--audio-format", "mp3")
        }
        if (platform == "YouTube") {
            return if (fmt == "webm") {
                val sel = when (quality) {
                    "1080p" -> "bestvideo[height<=1080][ext=webm]+bestaudio[ext=webm]/best[height<=1080][ext=webm]"
                    "720p" -> "bestvideo[height<=720][ext=webm]+bestaudio[ext=webm]/best[height<=720][ext=webm]"
                    else -> "bestvideo[ext=webm]+bestaudio[ext=webm]/best[ext=webm]/best"
                }
                listOf("-f", sel, "--merge-output-format", "webm")
            } else {
                val sel = when (quality) {
                    "1080p" -> "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]"
                    "720p" -> "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]"
                    else -> "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
                }
                listOf("-f", sel, "--merge-output-format", "mp4")
            }
        }
        // Bilibili / 其他：不限 ext
        val sel = when (quality) {
            "1080p" -> "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"
            "720p" -> "bestvideo[height<=720]+bestaudio/best[height<=720]/best"
            else -> "bestvideo+bestaudio/best"
        }
        return listOf("-f", sel, "--merge-output-format", fmt)
    }
}
