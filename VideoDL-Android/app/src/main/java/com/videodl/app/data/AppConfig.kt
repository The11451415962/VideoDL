package com.videodl.app.data

data class AppConfig(
    val saveDirUri: String = "",
    val proxyMode: String = "auto",
    val proxyUrl: String = "http://127.0.0.1:7897",
    val cookieMode: String = "none",
    val cookiePathUri: String = "",
    val defaultFormat: String = "mp4",
    val defaultQuality: String = "best",
    val autoOpenFile: Boolean = true,
)
