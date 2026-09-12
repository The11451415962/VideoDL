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
