package com.videodl.app.ui

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.widget.Toast
import androidx.core.content.FileProvider
import com.videodl.app.data.MediaTarget
import java.io.File

/**
 * 打开下载结果：相册里的是 content:// URI，未开相册时是本地文件路径，两种都要支持。
 * 首页和下载列表共用。
 */
internal fun openFile(ctx: Context, target: String) {
    try {
        val mime = when {
            target.endsWith(".m4a", true) || target.endsWith(".mp3", true) -> MediaTarget.AUDIO_MIME
            target.endsWith(".webm", true) -> "video/webm"
            else -> "video/*"
        }
        val uri: Uri = if (target.startsWith("content://")) {
            Uri.parse(target)
        } else {
            FileProvider.getUriForFile(ctx, "${ctx.packageName}.fileprovider", File(target))
        }
        ctx.startActivity(Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, mime)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        })
    } catch (e: Exception) {
        Toast.makeText(ctx, "无法打开文件: ${e.message}", Toast.LENGTH_SHORT).show()
    }
}

internal fun formatDuration(seconds: Int): String {
    if (seconds <= 0) return "?"
    val h = seconds / 3600
    val m = (seconds % 3600) / 60
    val s = seconds % 60
    return if (h > 0) "$h:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}"
    else "$m:${s.toString().padStart(2, '0')}"
}
