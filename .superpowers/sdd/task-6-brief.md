# Task 6: 引擎接口 YtdlpEngine + DownloadOptions + DownloadEvent

**Files:**
- 创建: `app/src/main/java/com/videodl/app/engine/DownloadOptions.kt`
- 创建: `app/src/main/java/com/videodl/app/engine/YtdlpEngine.kt`

**Interfaces:**
- 产出 `data class DownloadOptions`、`sealed class DownloadEvent`、`interface YtdlpEngine`。被 Task 7 实现，被 Task 8 DownloadService、Task 11 HomeViewModel 消费。

- [ ] **Step 1: 写 DownloadOptions + DownloadEvent + YtdlpEngine**

`engine/DownloadOptions.kt`:
```kotlin
package com.videodl.app.engine

data class DownloadOptions(
    val url: String,
    val outputPath: String,
    val proxyMode: String = "auto",
    val proxyUrl: String = "http://127.0.0.1:7897",
    val cookieMode: String = "none",
    val cookiePath: String = "",
    val format: String = "mp4",
    val quality: String = "best",
    val platform: String = "未知",
    val ffmpegLocation: String = "",
)
```

`engine/YtdlpEngine.kt`:
```kotlin
package com.videodl.app.engine

import kotlinx.coroutines.flow.Flow

sealed class DownloadEvent {
    object Started : DownloadEvent()
    data class Info(
        val title: String, val uploader: String,
        val duration: Int, val resolution: String,
    ) : DownloadEvent()
    data class Progress(val percent: Float, val speed: String, val eta: String) : DownloadEvent()
    data class Log(val line: String) : DownloadEvent()
    data class Finished(val filePath: String) : DownloadEvent()
    data class Error(val message: String) : DownloadEvent()
}

interface YtdlpEngine {
    fun fetchInfo(url: String, options: DownloadOptions): DownloadEvent.Info
    fun download(options: DownloadOptions): Flow<DownloadEvent>
    fun cancel()
}
```

- [ ] **Step 2: 编译通过**

Run: `./gradlew :app:compileDebugKotlin`
预期: BUILD SUCCESSFUL

- [ ] **Step 3: 提交**

```bash
git add app/src/main/java/com/videodl/app/engine
git commit -m "feat: YtdlpEngine interface + DownloadOptions + DownloadEvent"
```
