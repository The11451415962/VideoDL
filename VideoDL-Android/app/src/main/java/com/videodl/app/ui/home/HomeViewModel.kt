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
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

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
    val errorMessage: String = "",
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
        _state.update { it.copy(status = DownloadStatus.Fetching, logs = emptyList(), errorMessage = "") }
        viewModelScope.launch {
            val config = configRepo.configFlow.first()
            val baseDir = FileRepository.resolveBaseDir(getApplication(), config)
            // 先用占位名构建，拿到标题后再重建
            val options = DownloadOptions(
                url = s.url,
                outputPath = FileRepository.buildOutputPath(baseDir, "video", s.format, s.quality),
                proxyMode = s.proxyMode,
                proxyUrl = config.proxyUrl,
                cookieMode = config.cookieMode,
                cookiePath = config.cookiePathUri,
                format = s.format,
                quality = s.quality,
                platform = Platform.detect(s.url),
                ffmpegLocation = FileRepository.ffmpegLocation(getApplication()),
            )
            // fetchInfo 是同步网络解析，必须放 IO 线程，否则卡 UI
            val info = try {
                withContext(Dispatchers.IO) { engine.fetchInfo(s.url, options) }
            } catch (e: Exception) {
                null
            }
            // 用视频标题重建输出路径（与桌面版一致的命名）
            val finalOptions = info?.title
                ?.takeIf { it.isNotBlank() }
                ?.let { title ->
                    options.copy(outputPath = FileRepository.buildOutputPath(baseDir, title, s.format, s.quality))
                }
                ?: options
            if (info != null) {
                _state.update {
                    it.copy(videoInfo = VideoInfo(info.title, info.uploader, info.duration, info.resolution),
                           status = DownloadStatus.Downloading)
                }
            } else _state.update { it.copy(status = DownloadStatus.Downloading) }
            engine.download(finalOptions).collect { ev ->
                when (ev) {
                    is DownloadEvent.Progress -> _state.update { it.copy(percent = ev.percent, speed = ev.speed, eta = ev.eta) }
                    is DownloadEvent.Log -> _state.update { it.copy(logs = it.logs.takeLast(200) + ev.line) }
                    is DownloadEvent.Finished -> _state.update { it.copy(status = DownloadStatus.Done, percent = 100f, finishedFile = ev.filePath) }
                    is DownloadEvent.Error -> _state.update {
                        it.copy(status = DownloadStatus.Error, errorMessage = ev.message,
                                logs = it.logs.takeLast(200) + "错误：${ev.message}")
                    }
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
