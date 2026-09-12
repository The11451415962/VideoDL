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
    /** 下载完成后发布到系统相册/媒体库：剪映、相册等 App 直接可见，且无需任何存储权限 */
    val exportToGallery: Boolean = true,
)
