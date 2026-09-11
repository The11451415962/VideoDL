# Review Package - Task 8

## Base: 281088b  Head: 921c32b

## Commits
921c32b feat: foreground DownloadService + notification + FileRepository

## Diff stat
 VideoDL-Android/app/src/main/AndroidManifest.xml   |  12 +++
 .../java/com/videodl/app/data/FileRepository.kt    |  24 +++++
 .../com/videodl/app/service/DownloadService.kt     | 119 +++++++++++++++++++++
 .../com/videodl/app/data/FileRepositoryTest.kt     |  15 +++
 4 files changed, 170 insertions(+)

## Full diff
diff --git a/VideoDL-Android/app/src/main/AndroidManifest.xml b/VideoDL-Android/app/src/main/AndroidManifest.xml
index 8d6d4fc..4b321bd 100644
--- a/VideoDL-Android/app/src/main/AndroidManifest.xml
+++ b/VideoDL-Android/app/src/main/AndroidManifest.xml
@@ -22,5 +22,17 @@
                 <category android:name="android.intent.category.LAUNCHER"/>
             </intent-filter>
         </activity>
+
+        <activity android:name=".ShareReceiver" android:exported="true" android:theme="@android:style/Theme.Translucent.NoTitleBar">
+            <intent-filter>
+                <action android:name="android.intent.action.SEND"/>
+                <category android:name="android.intent.category.DEFAULT"/>
+                <data android:mimeType="text/plain"/>
+            </intent-filter>
+        </activity>
+
+        <service android:name=".service.DownloadService"
+            android:exported="false"
+            android:foregroundServiceType="dataSync"/>
     </application>
 </manifest>
diff --git a/VideoDL-Android/app/src/main/java/com/videodl/app/data/FileRepository.kt b/VideoDL-Android/app/src/main/java/com/videodl/app/data/FileRepository.kt
index cd4dd38..fd6416d 100644
--- a/VideoDL-Android/app/src/main/java/com/videodl/app/data/FileRepository.kt
+++ b/VideoDL-Android/app/src/main/java/com/videodl/app/data/FileRepository.kt
@@ -1,5 +1,8 @@
 package com.videodl.app.data
 
+import android.content.Context
+import java.io.File
+
 object Naming {
     /**
      * 在 dir 内生成不冲突的文件路径：base → base(2) → base(3)...
@@ -19,3 +22,24 @@ object Naming {
     fun sanitize(title: String): String =
         title.replace(Regex("[\\\\/:*?\"<>|]"), "_").trim()
 }
+
+object FileRepository {
+    fun ffmpegLocation(context: Context): String {
+        val target = File(context.filesDir, "ffmpeg")
+        if (target.exists()) return target.absolutePath
+        return ""
+    }
+
+    fun buildOutputPath(baseDir: String, config: AppConfig, url: String): String {
+        val safeBase = Naming.sanitize(File(url).nameWithoutExtension.ifBlank { "video" })
+        val ext = if (config.defaultFormat == "mp3") "mp3" else config.defaultFormat
+        val existing = File(baseDir).listFiles()?.map { it.name }?.toSet() ?: emptySet()
+        return Naming.nextFilePath(baseDir, safeBase, ext, existing)
+    }
+
+    fun defaultBaseDir(context: Context): String =
+        File(context.getExternalFilesDir(null), "VideoDL").apply { mkdirs() }.absolutePath
+
+    fun resolveBaseDir(context: Context, config: AppConfig): String =
+        config.saveDirUri.ifBlank { defaultBaseDir(context) }
+}
diff --git a/VideoDL-Android/app/src/main/java/com/videodl/app/service/DownloadService.kt b/VideoDL-Android/app/src/main/java/com/videodl/app/service/DownloadService.kt
new file mode 100644
index 0000000..7ee2f4e
--- /dev/null
+++ b/VideoDL-Android/app/src/main/java/com/videodl/app/service/DownloadService.kt
@@ -0,0 +1,119 @@
+package com.videodl.app.service
+
+import android.app.NotificationChannel
+import android.app.NotificationManager
+import android.app.Service
+import android.content.Context
+import android.content.Intent
+import android.os.Build
+import android.os.IBinder
+import androidx.core.app.NotificationCompat
+import com.videodl.app.MainApplication
+import com.videodl.app.data.AppConfig
+import com.videodl.app.data.ConfigRepositoryImpl
+import com.videodl.app.data.FileRepository
+import com.videodl.app.engine.DownloadEvent
+import com.videodl.app.engine.DownloadOptions
+import com.videodl.app.engine.Platform
+import kotlinx.coroutines.CoroutineScope
+import kotlinx.coroutines.Dispatchers
+import kotlinx.coroutines.Job
+import kotlinx.coroutines.flow.first
+import kotlinx.coroutines.flow.launchIn
+import kotlinx.coroutines.flow.onEach
+import kotlinx.coroutines.runBlocking
+
+class DownloadService : Service() {
+
+    private val scope = CoroutineScope(Dispatchers.Main + Job())
+    private var currentJob: Job? = null
+    private val notificationId = 1001
+
+    companion object {
+        const val ACTION_START = "com.videodl.app.START"
+        const val ACTION_CANCEL = "com.videodl.app.CANCEL"
+        const val EXTRA_URL = "url"
+
+        fun start(ctx: Context, url: String) {
+            ctx.startForegroundService(Intent(ctx, DownloadService::class.java).apply {
+                action = ACTION_START; putExtra(EXTRA_URL, url)
+            })
+        }
+        fun cancel(ctx: Context) {
+            ctx.startService(Intent(ctx, DownloadService::class.java).apply { action = ACTION_CANCEL })
+        }
+    }
+
+    override fun onBind(intent: Intent?): IBinder? = null
+
+    override fun onCreate() {
+        super.onCreate()
+        createChannel()
+        startForeground(notificationId, buildNotification("准备下载...", 0))
+    }
+
+    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
+        when (intent?.action) {
+            ACTION_START -> intent.getStringExtra(EXTRA_URL)?.let { startDownload(it) }
+            ACTION_CANCEL -> { currentJob?.cancel(); stopSelf() }
+        }
+        return START_NOT_STICKY
+    }
+
+    private fun startDownload(url: String) {
+        val engine = (application as MainApplication).engine
+        val config = runBlocking { ConfigRepositoryImpl(this@DownloadService).configFlow.first() }
+        val baseDir = FileRepository.resolveBaseDir(this, config)
+        val outputPath = FileRepository.buildOutputPath(baseDir, config, url)
+        val options = DownloadOptions(
+            url = url, outputPath = outputPath,
+            proxyMode = config.proxyMode, proxyUrl = config.proxyUrl,
+            cookieMode = config.cookieMode, cookiePath = config.cookiePathUri,
+            format = config.defaultFormat, quality = config.defaultQuality,
+            platform = Platform.detect(url),
+            ffmpegLocation = FileRepository.ffmpegLocation(this),
+        )
+        currentJob = engine.download(options).onEach { ev ->
+            when (ev) {
+                is DownloadEvent.Progress -> updateNotification(
+                    "${config.defaultFormat} ${config.defaultQuality}", ev.percent)
+                is DownloadEvent.Finished -> showComplete(ev.filePath)
+                is DownloadEvent.Error -> showError(ev.message)
+                else -> {}
+            }
+        }.launchIn(scope)
+    }
+
+    private fun createChannel() {
+        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
+            val ch = NotificationChannel("download", "下载进度", NotificationManager.IMPORTANCE_LOW)
+            (getSystemService(NOTIFICATION_SERVICE) as NotificationManager).createNotificationChannel(ch)
+        }
+    }
+
+    private fun buildNotification(text: String, percent: Int) = NotificationCompat.Builder(this, "download")
+        .setContentTitle("VideoDL 下载中").setContentText(text)
+        .setSmallIcon(android.R.drawable.stat_sys_download).setOngoing(true)
+        .setProgress(100, percent.coerceIn(0, 100), false).build()
+
+    private fun updateNotification(text: String, percent: Float) {
+        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
+        nm.notify(notificationId, buildNotification(text, percent.toInt()))
+    }
+
+    private fun showComplete(path: String) {
+        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
+        nm.notify(notificationId, NotificationCompat.Builder(this, "download")
+            .setContentTitle("下载完成").setContentText(path)
+            .setSmallIcon(android.R.drawable.stat_sys_download_done).setAutoCancel(true).build())
+        stopSelf()
+    }
+
+    private fun showError(msg: String) {
+        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
+        nm.notify(notificationId, NotificationCompat.Builder(this, "download")
+            .setContentTitle("下载失败").setContentText(msg)
+            .setSmallIcon(android.R.drawable.stat_notify_error).setAutoCancel(true).build())
+        stopSelf()
+    }
+}
diff --git a/VideoDL-Android/app/src/test/java/com/videodl/app/data/FileRepositoryTest.kt b/VideoDL-Android/app/src/test/java/com/videodl/app/data/FileRepositoryTest.kt
index b86902f..72f0507 100644
--- a/VideoDL-Android/app/src/test/java/com/videodl/app/data/FileRepositoryTest.kt
+++ b/VideoDL-Android/app/src/test/java/com/videodl/app/data/FileRepositoryTest.kt
@@ -2,6 +2,7 @@ package com.videodl.app.data
 
 import org.junit.Assert.*
 import org.junit.Test
+import java.io.File
 
 class NamingTest {
     @Test fun firstAvailable_noSuffix() {
@@ -16,3 +17,17 @@ class NamingTest {
         assertEquals("clean title", Naming.sanitize("clean title"))
     }
 }
+
+class FileRepositoryPureTest {
+    @Test fun buildOutputPath_firstNoSuffix() {
+        val dir = createTempDir().absolutePath
+        val c = AppConfig(defaultFormat = "mp4")
+        assertEquals("$dir/视频.mp4", FileRepository.buildOutputPath(dir, c, "https://x.com/视频"))
+    }
+    @Test fun buildOutputPath_conflictAddsSuffix() {
+        val dir = createTempDir()
+        dir.resolve("title.mp4").createNewFile()
+        val c = AppConfig(defaultFormat = "mp4")
+        assertEquals("${dir.absolutePath}/title(2).mp4", FileRepository.buildOutputPath(dir.absolutePath, c, "https://x.com/title"))
+    }
+}
