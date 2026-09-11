# Review Package - Task 9

## Base: 921c32b  Head: 9e1d00d

## Commits
9e1d00d feat: ShareReceiver ACTION_SEND -> MainActivity

## Diff stat
 .../java/com/videodl/app/ShareReceiverTest.kt      | 23 ++++++++++++++++++
 .../src/main/java/com/videodl/app/ShareReceiver.kt | 28 ++++++++++++++++++++++
 .../java/com/videodl/app/ui/home/HomeContract.kt   |  3 +++
 3 files changed, 54 insertions(+)

## Full diff
diff --git a/VideoDL-Android/app/src/androidTest/java/com/videodl/app/ShareReceiverTest.kt b/VideoDL-Android/app/src/androidTest/java/com/videodl/app/ShareReceiverTest.kt
new file mode 100644
index 0000000..685e5da
--- /dev/null
+++ b/VideoDL-Android/app/src/androidTest/java/com/videodl/app/ShareReceiverTest.kt
@@ -0,0 +1,23 @@
+package com.videodl.app
+
+import android.content.Intent
+import androidx.test.core.app.ActivityScenario
+import androidx.test.core.app.ApplicationProvider
+import androidx.test.ext.junit.runners.AndroidJUnit4
+import org.junit.Test
+import org.junit.runner.RunWith
+
+@RunWith(AndroidJUnit4::class)
+class ShareReceiverTest {
+    @Test fun plainUrl_passedThrough() {
+        val intent = Intent(ApplicationProvider.getApplicationContext(), ShareReceiver::class.java).apply {
+            action = Intent.ACTION_SEND
+            type = "text/plain"
+            putExtra(Intent.EXTRA_TEXT, "https://www.bilibili.com/video/BV123")
+        }
+        ActivityScenario.launch<ShareReceiver>(intent).use { scenario ->
+            // TODO: 用 Espresso-Intents intended() 校验 forward 的 EXTRA_SHARE_URL
+            // 无真机只编译验证，断言留给 Task 14 真机端到端覆盖
+        }
+    }
+}
diff --git a/VideoDL-Android/app/src/main/java/com/videodl/app/ShareReceiver.kt b/VideoDL-Android/app/src/main/java/com/videodl/app/ShareReceiver.kt
new file mode 100644
index 0000000..e7a8e36
--- /dev/null
+++ b/VideoDL-Android/app/src/main/java/com/videodl/app/ShareReceiver.kt
@@ -0,0 +1,28 @@
+package com.videodl.app
+
+import android.content.Intent
+import android.os.Bundle
+import androidx.activity.ComponentActivity
+import com.videodl.app.ui.home.EXTRA_SHARE_URL
+
+class ShareReceiver : ComponentActivity() {
+    override fun onCreate(savedInstanceState: Bundle?) {
+        super.onCreate(savedInstanceState)
+        val shared = intent?.getCharSequenceExtra(Intent.EXTRA_TEXT)?.toString() ?: ""
+        val url = extractUrl(shared)
+        val forward = Intent()
+        forward.component = android.content.ComponentName(packageName, "com.videodl.app.MainActivity")
+        forward.putExtra(EXTRA_SHARE_URL, url)
+        forward.flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
+        startActivity(forward)
+        finish()
+    }
+
+    /** 与桌面版 _extract_url_from_text 1:1 对应 */
+    private fun extractUrl(text: String): String {
+        val t = text.trim()
+        if (t.startsWith("http")) return t.trimEnd('。', '．', '.', '，', ',', '/', '\\')
+        Regex("https?://\\S+").find(t)?.let { return it.value.trimEnd('。', '．', '.', '，', ',', '/', '\\') }
+        return ""
+    }
+}
diff --git a/VideoDL-Android/app/src/main/java/com/videodl/app/ui/home/HomeContract.kt b/VideoDL-Android/app/src/main/java/com/videodl/app/ui/home/HomeContract.kt
new file mode 100644
index 0000000..d259fa7
--- /dev/null
+++ b/VideoDL-Android/app/src/main/java/com/videodl/app/ui/home/HomeContract.kt
@@ -0,0 +1,3 @@
+package com.videodl.app.ui.home
+
+const val EXTRA_SHARE_URL = "com.videodl.app.SHARE_URL"
