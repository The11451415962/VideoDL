# Task 11: HomeViewModel（主页状态机）

**Files:**
-（已存在）`app/src/main/java/com/videodl/app/ui/home/HomeContract.kt` — Task 9 已创建,跳过
- 创建: `app/src/main/java/com/videodl/app/ui/home/HomeViewModel.kt`
- 创建: `app/src/test/java/com/videodl/app/ui/home/HomeViewModelTest.kt`

**Interfaces:**
- 产出 `HomeUiState` 数据类 + `HomeViewModel`；被 Task 13 HomeScreen 消费。

## 关键协调要点

**HomeContract.kt 已存在**（Task 9 创建，含 `const val EXTRA_SHARE_URL = "com.videodl.app.SHARE_URL"`）。Step 1 无需重复创建——verify 它存在,直接跳到 Step 2。

HomeViewModel 依赖 `MainApplication.engine`（Chaquopy）— 全链路无法在 JVM 跑。test 只验证纯状态 reducer（HomeUiState.copy）,不构造 HomeViewModel。依赖 TDD 只构造纯数据。

- [ ] **Step 1: 确认 HomeContract.kt 存在**

Verify `app/src/main/java/com/videodl/app/ui/home/HomeContract.kt` 含 `EXTRA_SHARE_URL`。不存在才创建。

- [ ] **Step 2: 写 HomeViewModel**

```kotlin
package com.videodl.app.ui.home

import android.app.Application
import android.content.ClipboardManager
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.videodl.app.MainApplication
import com.videodl.app.data.AppConfig
import com.videodl.app.data.ConfigRepository
import com.videodl.app.data.ConfigRepositoryImpl
import com.videodl.app.data.FileRepository
import com.videodl.app.engine.DownloadEvent
import com.videodl.app.engine.DownloadOptions
import com.videodl.app.engine.Platform
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking

data class VideoInfo(
    val title: String, val uploader: String,
    val duration: Int, val resolution: String,
)

enum class DownloadStatus { Idle, Fetching, Downloading, Done, Error }

data class HomeUiState(
    val url: String = "",
    val videoInfo: VideoInfo? = null,
    val format: String = "mp4",
    val quality: String = "best",
    val proxyMode: String = "auto",
    val percent: Float = 0f,
    val speed: String = "",
    val eta: String = "",
    val status: DownloadStatus = DownloadStatus.Idle,
    val logs: List<String> = emptyList(),
    val finishedFile: String? = null,
)

class HomeViewModel(app: Application) : AndroidViewModel(app) {
    private val engine = (app as MainApplication).engine
    private val configRepo: ConfigRepository = ConfigRepositoryImpl(app)

    private val _state = MutableStateFlow(HomeUiState())
    val state: StateFlow<HomeUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            configRepo.configFlow.collect { cfg ->
                _state.update {
                    it.copy(proxyMode = cfg.proxyMode, format = cfg.defaultFormat,
                           quality = cfg.defaultQuality)
                }
            }
        }
    }

    fun onUrlChanged(url: String) = _state.update { it.copy(url = url) }
    fun onFormatChanged(fmt: String) = _state.update { it.copy(format = fmt) }
    fun onQualityChanged(q: String) = _state.update { it.copy(quality = q) }
    fun onProxyModeChanged(p: String) = _state.update { it.copy(proxyMode = p) }

    /** 系统分享直达入口：ShareReceiver 把 URL 带进来 */
    fun consumeSharedUrl(url: String) {
        if (url.isNotBlank()) { _state.update { it.copy(url = url) }; startDownload() }
    }

    fun startDownload() {
        val s = _state.value
        if (s.url.isBlank() || s.status == DownloadStatus.Downloading) return
        _state.update { it.copy(status = DownloadStatus.Fetching, logs = emptyList()) }
        val config = runBlocking { configRepo.configFlow.first() }
        val baseDir = FileRepository.resolveBaseDir(getApplication(), config)
        val options = DownloadOptions(
            url = s.url,
            outputPath = FileRepository.buildOutputPath(baseDir, config, s.url),
            proxyMode = s.proxyMode,
            proxyUrl = config.proxyUrl,
            cookieMode = config.cookieMode,
            cookiePath = config.cookiePath,
            format = s.format,
            quality = s.quality,
            platform = Platform.detect(s.url),
            ffmpegLocation = FileRepository.ffmpegLocation(getApplication()),
        )
        viewModelScope.launch {
            val info = try { engine.fetchInfo(s.url, options) } catch (e: Exception) { null }
            if (info != null) {
                _state.update {
                    it.copy(videoInfo = VideoInfo(info.title, info.uploader, info.duration, info.resolution),
                           status = DownloadStatus.Downloading)
                }
            } else _state.update { it.copy(status = DownloadStatus.Downloading) }
            engine.download(options).collect { ev ->
                when (ev) {
                    is DownloadEvent.Progress -> _state.update { it.copy(percent = ev.percent, speed = ev.speed, eta = ev.eta) }
                    is DownloadEvent.Log -> _state.update { it.copy(logs = it.logs.takeLast(200) + ev.line) }
                    is DownloadEvent.Finished -> _state.update { it.copy(status = DownloadStatus.Done, percent = 100f, finishedFile = ev.filePath) }
                    is DownloadEvent.Error -> _state.update { it.copy(status = DownloadStatus.Error) }
                    else -> {}
                }
            }
        }
    }

    fun cancel() { engine.cancel() }

    fun pasteFromClipboard() {
        val clipboard = getApplication<Application>()
            .getSystemService(android.content.Context.CLIPBOARD_SERVICE) as ClipboardManager
        val text = clipboard.primaryClip?.getItemAt(0)?.text?.toString() ?: return
        val url = extractUrl(text)
        if (url.isNotBlank()) _state.update { it.copy(url = url) }
    }

    /** 与桌面版 _extract_url_from_text 1:1 对应 */
    private fun extractUrl(text: String): String {
        val t = text.trim()
        if (t.startsWith("http")) return t.trimEnd('。', '．', '.', '，', ',', '/', '\\')
        Regex("https?://\\S+").find(t)?.let { return it.value.trimEnd('。', '．', '.', '，', ',', '/', '\\') }
        return ""
    }
}
```

- [ ] **Step 3: 写 HomeViewModelTest（JVM 单测，验证 reducer — 不构造 HomeViewModel）**

`app/src/test/java/com/videodl/app/ui/home/HomeViewModelTest.kt`:

```kotlin
package com.videodl.app.ui.home

import org.junit.Assert.assertEquals
import org.junit.Test

class HomeViewModelPureTest {
    @Test fun formatChanged_updatesState() {
        val s = HomeUiState()
        val next = s.copy(format = "mp3")
        assertEquals("mp3", next.format)
    }
    @Test fun initialState_isIdle() {
        val s = HomeUiState()
        assertEquals(DownloadStatus.Idle, s.status)
        assertEquals("", s.url)
    }
}
```

用 JUnit assertEquals（不引入 Turbine/guava）。

- [ ] **Step 4: 编译通过**

Run: `./gradlew :app:compileDebugKotlin`
预期: BUILD SUCCESSFUL

- [ ] **Step 5: 提交**

```bash
git add app/src/main/java/com/videodl/app/ui/home app/src/test
git commit -m "feat: HomeViewModel state machine"
```
