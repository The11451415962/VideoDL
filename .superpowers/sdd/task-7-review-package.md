# Review Package - Task 7

## Base: d1cdd08  Head: 281088b

## Commits
281088b feat: YtdlpEngineImpl via Chaquopy + MainApplication init

## Diff stat
 .../main/java/com/videodl/app/MainApplication.kt   | 15 +++-
 .../java/com/videodl/app/engine/YtdlpEngineImpl.kt | 90 ++++++++++++++++++++++
 2 files changed, 104 insertions(+), 1 deletion(-)

## Full diff
diff --git a/VideoDL-Android/app/src/main/java/com/videodl/app/MainApplication.kt b/VideoDL-Android/app/src/main/java/com/videodl/app/MainApplication.kt
index 08c92bc..9c60ca6 100644
--- a/VideoDL-Android/app/src/main/java/com/videodl/app/MainApplication.kt
+++ b/VideoDL-Android/app/src/main/java/com/videodl/app/MainApplication.kt
@@ -1,5 +1,18 @@
 package com.videodl.app
 
 import android.app.Application
+import com.chaquo.python.Python
+import com.chaquo.python.android.AndroidPlatform
+import com.videodl.app.engine.YtdlpEngine
+import com.videodl.app.engine.YtdlpEngineImpl
 
-class MainApplication : Application()
+class MainApplication : Application() {
+    lateinit var engine: YtdlpEngine
+        private set
+
+    override fun onCreate() {
+        super.onCreate()
+        if (!Python.isStarted()) Python.start(AndroidPlatform(this))
+        engine = YtdlpEngineImpl()
+    }
+}
diff --git a/VideoDL-Android/app/src/main/java/com/videodl/app/engine/YtdlpEngineImpl.kt b/VideoDL-Android/app/src/main/java/com/videodl/app/engine/YtdlpEngineImpl.kt
new file mode 100644
index 0000000..86ea7ae
--- /dev/null
+++ b/VideoDL-Android/app/src/main/java/com/videodl/app/engine/YtdlpEngineImpl.kt
@@ -0,0 +1,90 @@
+package com.videodl.app.engine
+
+import com.chaquo.python.Python
+import kotlinx.coroutines.Dispatchers
+import kotlinx.coroutines.channels.awaitClose
+import kotlinx.coroutines.flow.Flow
+import kotlinx.coroutines.flow.callbackFlow
+import kotlinx.coroutines.withContext
+import org.json.JSONObject
+
+class YtdlpEngineImpl : YtdlpEngine {
+
+    private val py: Python = Python.getInstance()
+    private val bridge = py.getModule("ytdlp_bridge")
+    @Volatile private var cancelled = false
+
+    /** 把 DownloadOptions 转成 yt-dlp args_list（复用 Task 3 已翻译的 Format / Proxy / Platform） */
+    private fun buildArgs(opts: DownloadOptions): List<String> {
+        val args = Format.resolve(opts.format, opts.quality, opts.platform).toMutableList()
+        if (opts.platform == "Bilibili") {
+            args += listOf("--add-header", "Referer:https://www.bilibili.com/",
+                          "--add-header", "Origin:https://www.bilibili.com")
+        }
+        ProxyResolver.resolve(opts.proxyMode, opts.proxyUrl, opts.url)?.let {
+            args += listOf("--proxy", it)
+        }
+        if (opts.cookieMode == "file" && opts.cookiePath.isNotBlank()) {
+            args += listOf("--cookies", opts.cookiePath)
+        }
+        args += listOf("--newline", "--no-playlist", "--playlist-items", "1")
+        return args
+    }
+
+    override fun fetchInfo(url: String, options: DownloadOptions): DownloadEvent.Info {
+        val args = buildArgs(options)
+        val jsonStr = bridge.callAttr("fetch_info", url, args).toString()
+        val obj = JSONObject(jsonStr)
+        if (obj.has("error")) throw RuntimeException(obj.getString("error"))
+        val w = obj.optInt("width", 0); val h = obj.optInt("height", 0)
+        return DownloadEvent.Info(
+            title = obj.optString("title", "未知标题"),
+            uploader = obj.optString("uploader", "未知"),
+            duration = obj.optInt("duration", 0),
+            resolution = if (w > 0) "${w}x${h}" else "?",
+        )
+    }
+
+    override fun download(options: DownloadOptions): Flow<DownloadEvent> = callbackFlow {
+        val args = buildArgs(options)
+        cancelled = false
+        // 注册 Kotlin→Python 回调（字符串 JSON 回调,见 Task 5 bridge）
+        bridge.callAttr("set_hooks",
+            com.chaquo.python.PyObject.fromJava { line: String ->
+                trySend(DownloadEvent.Log(line)); true
+            },
+            com.chaquo.python.PyObject.fromJava { jsonLine: String ->
+                try {
+                    val o = JSONObject(jsonLine)
+                    val pct = o.optDouble("percent", 0.0).toFloat()
+                    val speed = o.optString("speed", "")
+                    val eta = o.optString("eta", "")
+                    trySend(DownloadEvent.Progress(pct, speed, eta))
+                } catch (_: Exception) {}
+                true
+            }
+        )
+        withContext(Dispatchers.IO) {
+            try {
+                send(DownloadEvent.Started)
+                val resultStr = bridge.callAttr(
+                    "download", options.url, options.outputPath, args, options.ffmpegLocation
+                ).toString()
+                val res = JSONObject(resultStr)
+                if (cancelled) {
+                    send(DownloadEvent.Error("用户取消"))
+                } else if (res.getBoolean("ok")) {
+                    send(DownloadEvent.Finished(res.getString("path")))
+                } else {
+                    send(DownloadEvent.Error(res.optString("error", "下载失败")))
+                }
+            } catch (e: Exception) {
+                send(DownloadEvent.Error(e.message ?: "未知错误"))
+            }
+            close()
+        }
+        awaitClose { cancelled = true }
+    }
+
+    override fun cancel() { cancelled = true }
+}
