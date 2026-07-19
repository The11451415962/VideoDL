package com.videodl.app.engine

data class DownloadOptions(
    val url: String,
    val outputPath: String,
    val proxyMode: String = "auto",
    val proxyUrl: String = "http://127.0.0.1:7897",
    val cookieMode: String = "none",
    val cookiePath: String = "",
    val format: String = "mp4",
    val quality: String = "best",
    val platform: String = "未知",
    val ffmpegLocation: String = "",
)
