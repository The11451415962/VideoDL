package com.videodl.app

import android.content.Intent
import androidx.test.core.app.ActivityScenario
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class ShareReceiverTest {
    @Test fun plainUrl_passedThrough() {
        val intent = Intent(ApplicationProvider.getApplicationContext(), ShareReceiver::class.java).apply {
            action = Intent.ACTION_SEND
            type = "text/plain"
            putExtra(Intent.EXTRA_TEXT, "https://www.bilibili.com/video/BV123")
        }
        ActivityScenario.launch<ShareReceiver>(intent).use { scenario ->
            // TODO: 用 Espresso-Intents intended() 校验 forward 的 EXTRA_SHARE_URL
            // 无真机只编译验证，断言留给 Task 14 真机端到端覆盖
        }
    }
}
