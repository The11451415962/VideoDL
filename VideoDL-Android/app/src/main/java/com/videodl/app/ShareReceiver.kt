package com.videodl.app

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import com.videodl.app.ui.home.EXTRA_SHARE_URL

class ShareReceiver : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val shared = intent?.getCharSequenceExtra(Intent.EXTRA_TEXT)?.toString() ?: ""
        val url = extractUrl(shared)
        val forward = Intent()
        forward.component = android.content.ComponentName(packageName, "com.videodl.app.MainActivity")
        forward.putExtra(EXTRA_SHARE_URL, url)
        forward.flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        startActivity(forward)
        finish()
    }

    /** 与桌面版 _extract_url_from_text 1:1 对应 */
    private fun extractUrl(text: String): String {
        val t = text.trim()
        if (t.startsWith("http")) return t.trimEnd('。', '．', '.', '，', ',', '/', '\\')
        Regex("https?://\\S+").find(t)?.let { return it.value.trimEnd('。', '．', '.', '，', ',', '/', '\\') }
        return ""
    }
}
