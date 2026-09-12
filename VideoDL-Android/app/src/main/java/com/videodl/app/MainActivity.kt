package com.videodl.app

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.core.content.ContextCompat
import com.videodl.app.ui.VideoDlApp
import com.videodl.app.ui.home.EXTRA_SHARE_STARTED
import com.videodl.app.ui.home.EXTRA_SHARE_URL
import com.videodl.app.ui.home.HomeViewModel
import com.videodl.app.ui.openFile
import com.videodl.app.ui.theme.VideoDLTheme
import com.videodl.app.util.extractUrl

class MainActivity : ComponentActivity() {

    private val homeVm: HomeViewModel by viewModels()

    // 通知权限（Android 13+）
    private val notifPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { /* 用户选择后无需额外处理，Service 自行判断 */ }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // 请求通知权限（Android 13+）
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS)
                != PackageManager.PERMISSION_GRANTED
            ) {
                notifPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
        }

        // 处理系统分享直达
        handleShareIntent(intent)

        setContent {
            VideoDLTheme {
                VideoDlApp(
                    homeVm = homeVm,
                    onOpenFile = { target -> openFile(this, target) },
                )
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleShareIntent(intent)
    }

    private fun handleShareIntent(intent: Intent?) {
        if (intent == null) return
        // 1) ShareReceiver 转发来的已提取 URL
        val forwarded = intent.getStringExtra(EXTRA_SHARE_URL)
        // 2) 直接以 SEND 分享的原始文本
        val shared = if (intent.action == Intent.ACTION_SEND) {
            intent.getCharSequenceExtra(Intent.EXTRA_TEXT)?.toString() ?: ""
        } else ""
        val url = extractUrl(forwarded ?: shared)
        // ShareReceiver 通常已经直接启动了下载，这里只回填输入框，避免下两遍
        val startedByReceiver = intent.getBooleanExtra(EXTRA_SHARE_STARTED, false)
        if (url.isNotBlank()) homeVm.consumeSharedUrl(url, startNow = !startedByReceiver)
    }
}
