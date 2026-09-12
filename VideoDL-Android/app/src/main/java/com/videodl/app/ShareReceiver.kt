package com.videodl.app

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import com.videodl.app.service.DownloadService
import com.videodl.app.ui.home.EXTRA_SHARE_STARTED
import com.videodl.app.ui.home.EXTRA_SHARE_URL
import com.videodl.app.util.extractUrl

/**
 * 系统分享直达入口。
 *
 * 关键设计：**直接开下载**，不依赖 MainActivity 是否存活。
 * 之前是"转发给 MainActivity、由它启动下载" —— 实测踩到过：当 Activity 处于
 * 正在销毁或残留记录状态时，intent 被投给残留记录（result code=3），
 * onCreate 都没跑，分享静默失效，什么都不会发生。
 */
class ShareReceiver : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val shared = intent?.getCharSequenceExtra(Intent.EXTRA_TEXT)?.toString() ?: ""
        val url = extractUrl(shared)

        if (url.isNotBlank()) {
            // format / quality / proxy 留空 = 由下载服务按用户当前配置决定
            runCatching { DownloadService.start(this, url) }
        }

        // 再把界面带到前台展示进度（同时把链接传给输入框显示出来）
        val forward = Intent(this, MainActivity::class.java).apply {
            putExtra(EXTRA_SHARE_URL, url)
            putExtra(EXTRA_SHARE_STARTED, url.isNotBlank())
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        runCatching { startActivity(forward) }
        finish()
    }
}
