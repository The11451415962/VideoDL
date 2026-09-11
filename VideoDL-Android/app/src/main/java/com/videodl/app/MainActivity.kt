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
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.core.content.ContextCompat
import androidx.lifecycle.viewmodel.compose.viewModel
import com.videodl.app.ui.home.EXTRA_SHARE_URL
import com.videodl.app.ui.home.HomeScreen
import com.videodl.app.ui.home.HomeViewModel
import com.videodl.app.ui.settings.SettingsScreen
import com.videodl.app.ui.settings.SettingsViewModel
import com.videodl.app.ui.theme.VideoDLTheme

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
                var showSettings by remember { mutableStateOf(false) }
                val settingsVm: SettingsViewModel = viewModel()

                if (showSettings) {
                    SettingsScreen(
                        vm = settingsVm,
                        onBack = { showSettings = false },
                    )
                } else {
                    HomeScreen(
                        vm = homeVm,
                        onOpenSettings = { showSettings = true },
                    )
                }
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
        if (url.isNotBlank()) homeVm.consumeSharedUrl(url)
    }

    /** 与桌面版 _extract_url_from_text 1:1 对应 */
    private fun extractUrl(text: String): String {
        val t = text.trim()
        if (t.startsWith("http")) return t.trimEnd('。', '．', '.', '，', ',', '/', '\\')
        Regex("https?://\\S+").find(t)?.let { return it.value.trimEnd('。', '．', '.', '，', ',', '/', '\\') }
        return ""
    }
}
