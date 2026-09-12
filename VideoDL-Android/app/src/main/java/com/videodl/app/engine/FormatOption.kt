package com.videodl.app.engine

/**
 * 一个可选的下载格式（对应 yt-dlp 的一个 format）。
 *
 * UI 上的"格式选择"底部弹窗就是把这些渲染成卡片：
 * 主标签（分辨率/仅音频）+ 备注 + 一排小标签（编码/体积/码率）。
 */
data class FormatOption(
    val id: String,
    val label: String,
    val note: String,
    val ext: String,
    val vcodec: String,
    val acodec: String,
    val height: Int,
    val fps: Int,
    val sizeBytes: Long,
    val tbr: Double,
    val abr: Double,
    val audioOnly: Boolean,
    val width: Int = 0,
) {
    /** 给用户看的体积，例如 "12.3 MB"；未知返回 "" */
    val sizeText: String
        get() = if (sizeBytes > 0) formatBytes(sizeBytes) else ""

    /** 一排小标签里的编码说明，例如 "avc1 · mp4a" */
    val codecText: String
        get() {
            val v = vcodec.substringBefore('.').takeIf { it.isNotBlank() && it != "none" }
            val a = acodec.substringBefore('.').takeIf { it.isNotBlank() && it != "none" }
            return listOfNotNull(v, a).joinToString(" · ")
        }

    val bitrateText: String
        get() {
            val kbps = if (audioOnly) abr else tbr
            return if (kbps > 0) "${kbps.toInt()}k" else ""
        }

    /** 分辨率文字，例如 "1080×1920"；竖屏视频也照实显示 */
    val resolutionText: String
        get() = if (width > 0 && height > 0) "${width}×${height}" else ""

    /**
     * 画质标签。竖屏视频按**短边**叫法（1080×1920 → "1080p"）——
     * 平台和用户都是这么说的，写成 1920p 会让人以为画质更高。
     */
    val qualityLabel: String
        get() {
            if (audioOnly) return "audio"
            val short = when {
                width > 0 && height > 0 -> minOf(width, height)
                else -> height
            }
            return if (short > 0) "${short}p" else "best"
        }

    /**
     * 手机剪辑 App（剪映/相册）能不能吃下这个流。
     * H.264 视频 + AAC 音频才稳；HEVC/AV1/Opus 经常被拒。
     */
    val editorFriendly: Boolean
        get() = when {
            audioOnly -> acodec.startsWith("mp4a") || acodec.startsWith("aac")
            else -> vcodec.startsWith("avc1") || vcodec.startsWith("h264")
        }

    /**
     * 实际交给 yt-dlp 的格式选择器。
     *
     * 关键：**纯视频流必须拼音频**，否则下出来是没声音的视频
     * （实测点中 hvc1 1080P 就是这样）。音频优先挑 AAC。
     */
    val downloadSelector: String
        get() = if (!audioOnly && acodec == "none" && vcodec != "none" && id.isNotBlank()) {
            "$id+bestaudio[acodec^=mp4a]/$id+bestaudio/$id"
        } else {
            id
        }

    companion object {
        fun formatBytes(n: Long): String {
            if (n <= 0) return ""
            val units = listOf("B", "KB", "MB", "GB", "TB")
            var v = n.toDouble()
            var i = 0
            while (v >= 1024 && i < units.lastIndex) {
                v /= 1024.0
                i++
            }
            return if (i == 0) "${v.toInt()} ${units[i]}" else String.format("%.1f %s", v, units[i])
        }
    }
}
