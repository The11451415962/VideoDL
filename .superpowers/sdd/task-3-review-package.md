# Review Package - Task 3

## Base: 47ebafb  Head: 447fa4c

## Commits
447fa4c feat: port format/platform/proxy logic from desktop to Kotlin

## Diff stat
 .../java/com/videodl/app/engine/FormatResolver.kt  | 54 ++++++++++++++++++++++
 .../com/videodl/app/engine/FormatResolverTest.kt   | 37 +++++++++++++++
 .../com/videodl/app/engine/ProxyResolverTest.kt    | 21 +++++++++
 3 files changed, 112 insertions(+)

## Full diff
diff --git a/VideoDL-Android/app/src/main/java/com/videodl/app/engine/FormatResolver.kt b/VideoDL-Android/app/src/main/java/com/videodl/app/engine/FormatResolver.kt
new file mode 100644
index 0000000..dbb80ec
--- /dev/null
+++ b/VideoDL-Android/app/src/main/java/com/videodl/app/engine/FormatResolver.kt
@@ -0,0 +1,54 @@
+package com.videodl.app.engine
+
+object Platform {
+    fun detect(url: String): String = when {
+        url.contains("youtube.com", true) || url.contains("youtu.be", true) -> "YouTube"
+        url.contains("bilibili.com", true) || url.contains("b23.tv", true) -> "Bilibili"
+        url.contains("douyin.com", true) || url.contains("tiktok.com", true) -> "抖音"
+        else -> "未知"
+    }
+}
+
+object ProxyResolver {
+    fun resolve(proxyMode: String, proxyUrl: String, url: String): String? = when (proxyMode) {
+        "direct" -> null
+        "proxy" -> proxyUrl
+        else -> if (Platform.detect(url) == "YouTube") proxyUrl else null  // auto
+    }
+}
+
+object Format {
+    /**
+     * 返回 yt-dlp 的 format 参数 key-value 对（顺序相关），
+     * 与桌面版 resolve_format_string 一一对应。platform = Platform.detect(url)。
+     */
+    fun resolve(fmt: String, quality: String, platform: String): List<String> {
+        if (fmt == "mp3" || quality == "audio") {
+            return listOf("-f", "bestaudio/best", "--audio-format", "mp3")
+        }
+        if (platform == "YouTube") {
+            return if (fmt == "webm") {
+                val sel = when (quality) {
+                    "1080p" -> "bestvideo[height<=1080][ext=webm]+bestaudio[ext=webm]/best[height<=1080][ext=webm]"
+                    "720p" -> "bestvideo[height<=720][ext=webm]+bestaudio[ext=webm]/best[height<=720][ext=webm]"
+                    else -> "bestvideo[ext=webm]+bestaudio[ext=webm]/best[ext=webm]/best"
+                }
+                listOf("-f", sel, "--merge-output-format", "webm")
+            } else {
+                val sel = when (quality) {
+                    "1080p" -> "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]"
+                    "720p" -> "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]"
+                    else -> "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
+                }
+                listOf("-f", sel, "--merge-output-format", "mp4")
+            }
+        }
+        // Bilibili / 其他：不限 ext
+        val sel = when (quality) {
+            "1080p" -> "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"
+            "720p" -> "bestvideo[height<=720]+bestaudio/best[height<=720]/best"
+            else -> "bestvideo+bestaudio/best"
+        }
+        return listOf("-f", sel, "--merge-output-format", fmt)
+    }
+}
diff --git a/VideoDL-Android/app/src/test/java/com/videodl/app/engine/FormatResolverTest.kt b/VideoDL-Android/app/src/test/java/com/videodl/app/engine/FormatResolverTest.kt
new file mode 100644
index 0000000..e295889
--- /dev/null
+++ b/VideoDL-Android/app/src/test/java/com/videodl/app/engine/FormatResolverTest.kt
@@ -0,0 +1,37 @@
+package com.videodl.app.engine
+
+import org.junit.Assert.*
+import org.junit.Test
+
+class PlatformTest {
+    @Test fun youtube() {
+        assertEquals("YouTube", Platform.detect("https://www.youtube.com/watch?v=abc"))
+        assertEquals("YouTube", Platform.detect("https://youtu.be/abc"))
+    }
+    @Test fun bilibili() {
+        assertEquals("Bilibili", Platform.detect("https://www.bilibili.com/video/BV123"))
+        assertEquals("Bilibili", Platform.detect("https://b23.tv/xyz"))
+    }
+    @Test fun douyin() {
+        assertEquals("抖音", Platform.detect("https://v.douyin.com/abc"))
+        assertEquals("抖音", Platform.detect("https://www.tiktok.com/@x/video/1"))
+    }
+    @Test fun unknown() {
+        assertEquals("未知", Platform.detect("https://example.com/v"))
+    }
+}
+
+class ProxyResolverTest {
+    @Test fun direct_returnsNull() {
+        assertNull(ProxyResolver.resolve("direct", "http://127.0.0.1:7897", "https://youtube.com/v"))
+    }
+    @Test fun proxy_alwaysReturnsUrl() {
+        assertEquals("http://127.0.0.1:7897",
+            ProxyResolver.resolve("proxy", "http://127.0.0.1:7897", "https://bilibili.com/v"))
+    }
+    @Test fun auto_youtubeReturnsUrl_bilibiliReturnsNull() {
+        assertEquals("http://127.0.0.1:7897",
+            ProxyResolver.resolve("auto", "http://127.0.0.1:7897", "https://youtube.com/v"))
+        assertNull(ProxyResolver.resolve("auto", "http://127.0.0.1:7897", "https://bilibili.com/v"))
+    }
+}
diff --git a/VideoDL-Android/app/src/test/java/com/videodl/app/engine/ProxyResolverTest.kt b/VideoDL-Android/app/src/test/java/com/videodl/app/engine/ProxyResolverTest.kt
new file mode 100644
index 0000000..37fe9cc
--- /dev/null
+++ b/VideoDL-Android/app/src/test/java/com/videodl/app/engine/ProxyResolverTest.kt
@@ -0,0 +1,21 @@
+package com.videodl.app.engine
+
+import org.junit.Assert.*
+import org.junit.Test
+
+class FormatTest {
+    @Test fun audio_returnsMp3() {
+        assertEquals(listOf("-f", "bestaudio/best", "--audio-format", "mp3"),
+            Format.resolve("mp4", "audio", "YouTube"))
+    }
+    @Test fun youtube_best_mp4() {
+        val r = Format.resolve("mp4", "best", "YouTube")
+        assertTrue(r.joinToString().contains("[ext=mp4]"))
+        assertTrue(r.joinToString().contains("--merge-output-format"))
+    }
+    @Test fun bilibili_noExtFilter() {
+        val r = Format.resolve("mp4", "1080p", "Bilibili")
+        assertFalse(r.joinToString().contains("ext="))
+        assertTrue(r.joinToString().contains("height<=1080"))
+    }
+}
