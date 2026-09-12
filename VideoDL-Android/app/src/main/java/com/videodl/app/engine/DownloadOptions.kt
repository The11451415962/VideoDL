package com.videodl.app.engine

data class DownloadOptions(
    val url: String,
    val outputPath: String,
    val proxyMode: String = "auto",
    val proxyUrl: String = "http://127.0.0.1:7890",
    val cookieMode: String = "none",
    val cookiePath: String = "",
    val format: String = "mp4",
    val quality: String = "best",
    val platform: String = "未知",
    val ffmpegLocation: String = "",
    /**
     * 用户在"格式选择"里挑中的具体格式（例如 "30080+30280"）。
     * 非空时直接用它覆盖按格式/画质推导出来的选择器。
     */
    val formatSelector: String = "",
)
