# Task 8: 前台 DownloadService + 通知栏进度 + FileRepository 完善

**Files:**
- 创建: `app/src/main/java/com/videodl/app/service/DownloadService.kt`
- 修改: `app/src/main/java/com/videodl/app/data/FileRepository.kt`（补 ffmpegLocation + buildOutputPath 等）
- 修改: `app/src/main/AndroidManifest.xml`（注册 `<service>` + ShareReceiver）
- 创建: `app/src/test/java/com/videodl/app/data/FileRepositoryTest.kt`

**Interfaces:**
- 产出 `DownloadService`（`companion object` 含 `start`/`cancel`）；被 Task 11 HomeViewModel 消费。

## 关键协调要点（读 before starting）

1. **FileRepository.kt 已存在**（Task 4 写入的 `object Naming`，含 `nextFilePath` + `sanitize`）。Step 2 的代码是"补全"——你必须在**同一个文件**里**合并** Task 4 的 `Naming` 对象 + 新增的 `ffmpegLocation` / `buildOutputPath` / `defaultBaseDir` / `resolveBaseDir` 函数。不要覆盖掉 Naming。最终 FileRepository.kt 应同时包含 `object Naming` 和这些顶层函数。

2. **DownloadService 应使用重构后的签名**。Step 1 的代码片段里写的是 `FileRepository.buildOutputPath(this, config, url)`（旧签名），但 Step 2 把 buildOutputPath 重构为 `buildOutputPath(baseDir: String, config, url)` + `resolveBaseDir(context, config)`。**DownloadService 里请用新签名**：
   ```kotlin
   val baseDir = FileRepository.resolveBaseDir(this, config)
   val outputPath = FileRepository.buildOutputPath(baseDir, config, url)
   ```
   这样 Step 1 和 Step 2 才能协同。

3. **FileRepositoryPureTest 用 JUnit assertEquals**（不要引入 com.google.common.truth 新依赖）。测试 `buildOutputPath(baseDir, config, url)` 这个纯函数。

- [ ] **Step 1: 写 DownloadService**

```kotlin
package com.videodl.app.service

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.videodl.app.MainApplication
import com.videodl.app.data.AppConfig
import com.videodl.app.data.ConfigRepositoryImpl
import com.videodl.app.data.FileRepository
import com.videodl.app.engine.DownloadEvent
import com.videodl.app.engine.DownloadOptions
import com.videodl.app.engine.Platform
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.runBlocking

class DownloadService : Service() {

    private val scope = CoroutineScope(Dispatchers.Main + Job())
    private var currentJob: Job? = null
    private val notificationId = 1001

    companion object {
        const val ACTION_START = "com.videodl.app.START"
        const val ACTION_CANCEL = "com.videodl.app.CANCEL"
        const val EXTRA_URL = "url"

        fun start(ctx: Context, url: String) {
            ctx.startForegroundService(Intent(ctx, DownloadService::class.java).apply {
                action = ACTION_START; putExtra(EXTRA_URL, url)
            })
        }
        fun cancel(ctx: Context) {
            ctx.startService(Intent(ctx, DownloadService::class.java).apply { action = ACTION_CANCEL })
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createChannel()
        startForeground(notificationId, buildNotification("准备下载...", 0))
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> intent.getStringExtra(EXTRA_URL)?.let { startDownload(it) }
            ACTION_CANCEL -> { currentJob?.cancel(); stopSelf() }
        }
        return START_NOT_STICKY
    }

    private fun startDownload(url: String) {
        val engine = (application as MainApplication).engine
        val config = runBlocking { ConfigRepositoryImpl(this@DownloadService).configFlow.first() }
        val baseDir = FileRepository.resolveBaseDir(this, config)
        val outputPath = FileRepository.buildOutputPath(baseDir, config, url)
        val options = DownloadOptions(
            url = url, outputPath = outputPath,
            proxyMode = config.proxyMode, proxyUrl = config.proxyUrl,
            cookieMode = config.cookieMode, cookiePath = config.cookiePath,
            format = config.defaultFormat, quality = config.defaultQuality,
            platform = Platform.detect(url),
            ffmpegLocation = FileRepository.ffmpegLocation(this),
        )
        currentJob = engine.download(options).onEach { ev ->
            when (ev) {
                is DownloadEvent.Progress -> updateNotification(
                    "${config.defaultFormat} ${config.quality}", ev.percent)
                is DownloadEvent.Finished -> showComplete(ev.filePath)
                is DownloadEvent.Error -> showError(ev.message)
                else -> {}
            }
        }.launchIn(scope)
    }

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val ch = NotificationChannel("download", "下载进度", NotificationManager.IMPORTANCE_LOW)
            (getSystemService(NOTIFICATION_SERVICE) as NotificationManager).createNotificationChannel(ch)
        }
    }

    private fun buildNotification(text: String, percent: Int) = NotificationCompat.Builder(this, "download")
        .setContentTitle("VideoDL 下载中").setContentText(text)
        .setSmallIcon(android.R.drawable.stat_sys_download).setOngoing(true)
        .setProgress(100, percent.coerceIn(0, 100), false).build()

    private fun updateNotification(text: String, percent: Float) {
        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(notificationId, buildNotification(text, percent.toInt()))
    }

    private fun showComplete(path: String) {
        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(notificationId, NotificationCompat.Builder(this, "download")
            .setContentTitle("下载完成").setContentText(path)
            .setSmallIcon(android.R.drawable.stat_sys_download_done).setAutoCancel(true).build())
        stopSelf()
    }

    private fun showError(msg: String) {
        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(notificationId, NotificationCompat.Builder(this, "download")
            .setContentTitle("下载失败").setContentText(msg)
            .setSmallIcon(android.R.drawable.stat_notify_error).setAutoCancel(true).build())
        stopSelf()
    }
}
```

- [ ] **Step 2: FileRepository 补全（合并 Task 4 Naming + 新函数）**

最终 `app/src/main/java/com/videodl/app/data/FileRepository.kt` 应包含：

```kotlin
package com.videodl.app.data

import android.content.Context
import java.io.File

object Naming {
    fun nextFilePath(dir: String, base: String, ext: String,
                     existing: Set<String> = emptySet(), startAt: Int = 1): String {
        var idx = startAt
        while (true) {
            val name = if (idx == 1) "$base.$ext" else "$base($idx).$ext"
            if (name !in existing) return "$dir/$name"
            idx++
        }
    }

    fun sanitize(title: String): String =
        title.replace(Regex("[\\\\/:*?\"<>|]"), "_").trim()
}

object FileRepository {
    fun ffmpegLocation(context: Context): String {
        val target = File(context.filesDir, "ffmpeg")
        if (target.exists()) return target.absolutePath
        return ""
    }

    fun buildOutputPath(baseDir: String, config: AppConfig, url: String): String {
        val safeBase = Naming.sanitize(File(url).nameWithoutExtension.ifBlank { "video" })
        val ext = if (config.defaultFormat == "mp3") "mp3" else config.defaultFormat
        val existing = File(baseDir).listFiles()?.map { it.name }?.toSet() ?: emptySet()
        return Naming.nextFilePath(baseDir, safeBase, ext, existing)
    }

    fun defaultBaseDir(context: Context): String =
        File(context.getExternalFilesDir(null), "VideoDL").apply { mkdirs() }.absolutePath

    fun resolveBaseDir(context: Context, config: AppConfig): String =
        config.saveDirUri.ifBlank { defaultBaseDir(context) }
}
```

- [ ] **Step 3: 写 FileRepositoryPureTest（JVM 单测，用 JUnit assertEquals）**

`app/src/test/java/com/videodl/app/data/FileRepositoryTest.kt`：

```kotlin
package com.videodl.app.data

import com.google.common.truth.Truth.assertThat
import org.junit.Test
import java.io.File

class FileRepositoryPureTest {
    @Test fun buildOutputPath_firstNoSuffix() {
        val dir = createTempDir().absolutePath
        val c = AppConfig(defaultFormat = "mp4")
        assertThat(FileRepository.buildOutputPath(dir, c, "https://x.com/视频"))
            .isEqualTo("$dir/视频.mp4")
    }
    @Test fun buildOutputPath_conflictAddsSuffix() {
        val dir = createTempDir()
        dir.resolve("title.mp4").createNewFile()
        val c = AppConfig(defaultFormat = "mp4")
        assertThat(FileRepository.buildOutputPath(dir.absolutePath, c, "https://x.com/title"))
            .isEqualTo("${dir.absolutePath}/title(2).mp4")
    }
}
```

> 注：`com.google.common.truth.Truth` 需要 guava 依赖。如果 `testImplementation("com.google.guava:guava:32.1.3-jre")` 不在 build.gradle.kts 里，请加到 dependencies 块。或者改用 JUnit 的 `org.junit.Assert.assertEquals`（无需新依赖）。**推荐用 JUnit assertEquals 以避免引入新依赖。**

- [ ] **Step 4: AndroidManifest.xml 注册 Service + ShareReceiver**

在 `<application>` 内补：

```xml
<activity android:name=".ShareReceiver" android:exported="true" android:theme="@android:style/Theme.Translucent.NoTitleBar">
    <intent-filter>
        <action android:name="android.intent.action.SEND"/>
        <category android:name="android.intent.category.DEFAULT"/>
        <data android:mimeType="text/plain"/>
    </intent-filter>
</activity>

<service android:name=".service.DownloadService"
    android:exported="false"
    android:foregroundServiceType="dataSync"/>
```

- [ ] **Step 5: 跑测试 + 编译**

Run: `./gradlew :app:testDebugUnitTest --tests "com.videodl.app.data.*"` 和 `./gradlew :app:assembleDebug`
预期: PASS + BUILD SUCCESSFUL

- [ ] **Step 6: 提交**

```bash
git add app
git commit -m "feat: foreground DownloadService + notification + FileRepository"
```
