# Review Package - Task 6

## Base: 1f65c76  Head: d1cdd08

## Commits
d1cdd08 feat: YtdlpEngine interface + DownloadOptions + DownloadEvent

## Diff stat
 .../java/com/videodl/app/engine/DownloadOptions.kt  | 14 ++++++++++++++
 .../main/java/com/videodl/app/engine/YtdlpEngine.kt | 21 +++++++++++++++++++++
 2 files changed, 35 insertions(+)

## Full diff
diff --git a/VideoDL-Android/app/src/main/java/com/videodl/app/engine/DownloadOptions.kt b/VideoDL-Android/app/src/main/java/com/videodl/app/engine/DownloadOptions.kt
new file mode 100644
index 0000000..d6eedb2
--- /dev/null
+++ b/VideoDL-Android/app/src/main/java/com/videodl/app/engine/DownloadOptions.kt
@@ -0,0 +1,14 @@
+package com.videodl.app.engine
+
+data class DownloadOptions(
+    val url: String,
+    val outputPath: String,
+    val proxyMode: String = "auto",
+    val proxyUrl: String = "http://127.0.0.1:7897",
+    val cookieMode: String = "none",
+    val cookiePath: String = "",
+    val format: String = "mp4",
+    val quality: String = "best",
+    val platform: String = "未知",
+    val ffmpegLocation: String = "",
+)
diff --git a/VideoDL-Android/app/src/main/java/com/videodl/app/engine/YtdlpEngine.kt b/VideoDL-Android/app/src/main/java/com/videodl/app/engine/YtdlpEngine.kt
new file mode 100644
index 0000000..54ac389
--- /dev/null
+++ b/VideoDL-Android/app/src/main/java/com/videodl/app/engine/YtdlpEngine.kt
@@ -0,0 +1,21 @@
+package com.videodl.app.engine
+
+import kotlinx.coroutines.flow.Flow
+
+sealed class DownloadEvent {
+    object Started : DownloadEvent()
+    data class Info(
+        val title: String, val uploader: String,
+        val duration: Int, val resolution: String,
+    ) : DownloadEvent()
+    data class Progress(val percent: Float, val speed: String, val eta: String) : DownloadEvent()
+    data class Log(val line: String) : DownloadEvent()
+    data class Finished(val filePath: String) : DownloadEvent()
+    data class Error(val message: String) : DownloadEvent()
+}
+
+interface YtdlpEngine {
+    fun fetchInfo(url: String, options: DownloadOptions): DownloadEvent.Info
+    fun download(options: DownloadOptions): Flow<DownloadEvent>
+    fun cancel()
+}
