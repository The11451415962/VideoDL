package com.videodl.app.ui.home

import android.app.Application
import android.content.ClipboardManager
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.videodl.app.MainApplication
import com.videodl.app.data.ConfigRepository
import com.videodl.app.data.ConfigRepositoryImpl
import com.videodl.app.data.DownloadCenter
import com.videodl.app.data.DownloadStatus
import com.videodl.app.data.VideoInfo
import com.videodl.app.engine.DownloadOptions
import com.videodl.app.engine.FormatOption
import com.videodl.app.engine.Platform
import com.videodl.app.service.DownloadService
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

data class HomeUiState(
    val url: String = "",
    /** 正在抓取信息/格式 */
    val fetching: Boolean = false,
    val fetchError: String = "",
    val info: VideoInfo? = null,
    val thumbnail: String = "",
    val formats: List<FormatOption> = emptyList(),
    /** 当前下载（来自 DownloadCenter） */
    val percent: Float = 0f,
    val speed: String = "",
    val eta: String = "",
    val status: DownloadStatus = DownloadStatus.Idle,
    val logs: List<String> = emptyList(),
    val finishedFile: String? = null,
    val errorMessage: String = "",
    val autoOpenFile: Boolean = true,
    val destination: String = "",
) {
    val busy: Boolean
        get() = status == DownloadStatus.Downloading || status == DownloadStatus.Fetching
}

/**
 * 首页（新建下载）的状态与动作。
 *
 * 流程对齐 YTDLnis：粘贴链接 → 抓取 → 结果卡片（缩略图/标题/时长）
 * → 选格式（底部弹窗）或直接"下载视频 / 仅音频" → 交给前台 Service 下载。
 */
class HomeViewModel(app: Application) : AndroidViewModel(app) {
    private val appCtx: Application = app
    private val engine = (app as MainApplication).engine
    private val configRepo: ConfigRepository = ConfigRepositoryImpl(app)

    private val selection = MutableStateFlow(HomeUiState())

    val state: StateFlow<HomeUiState> = combine(selection, DownloadCenter.state) { sel, dl ->
        sel.copy(
            percent = dl.percent,
            speed = dl.speed,
            eta = dl.eta,
            status = dl.status,
            logs = dl.logs,
            finishedFile = dl.finishedUri ?: sel.finishedFile,
            errorMessage = dl.error,
            destination = dl.destination.ifBlank { sel.destination },
        )
    }.stateIn(viewModelScope, SharingStarted.Eagerly, HomeUiState())

    init {
        viewModelScope.launch {
            configRepo.configFlow.collect { cfg ->
                selection.update {
                    it.copy(autoOpenFile = cfg.autoOpenFile)
                }
            }
        }
    }

    fun onUrlChanged(url: String) {
        selection.update { it.copy(url = url, fetchError = "") }
    }

    /**
     * 系统分享直达。
     *
     * @param startNow 由 ShareReceiver 分享过来时是 false —— 下载已经在分享入口启动了，
     *   这里只回填链接并抓一次信息把结果卡片显示出来；
     *   其它入口（直接把 SEND 发给界面）才由这里启动。
     */
    fun consumeSharedUrl(url: String, startNow: Boolean = true) {
        if (url.isBlank()) return
        selection.update { it.copy(url = url, fetchError = "") }
        fetch()
        if (startNow) startDownload()
    }

    /** 抓取链接信息 + 可选格式（结果卡片和格式弹窗的数据源） */
    fun fetch() {
        val s = selection.value
        val url = s.url.trim()
        if (url.isBlank() || s.fetching) return
        selection.update { it.copy(fetching = true, fetchError = "", info = null, formats = emptyList()) }
        viewModelScope.launch {
            val cfg = configRepo.configFlow.first()
            val opts = baseOptions(url, cfg)
            val result = runCatching {
                withContext(Dispatchers.IO) { engine.fetchDetail(url, opts) }
            }
            result.onSuccess { detail ->
                selection.update {
                    it.copy(
                        fetching = false,
                        info = VideoInfo(detail.title, detail.uploader, detail.duration, ""),
                        thumbnail = detail.thumbnail,
                        formats = detail.formats,
                    )
                }
            }.onFailure { e ->
                selection.update {
                    it.copy(fetching = false, fetchError = e.message ?: "抓取失败")
                }
            }
        }
    }

    /** 打开格式弹窗前的准备（格式已在抓取时拿到） */
    fun formats(): List<FormatOption> = selection.value.formats

    /** 开始下载：selector 为空表示按画质档位自动挑（H.264/AAC 优先） */
    fun startDownload(
        selector: String = "",
        formatOverride: String = "",
    ) {
        val s = selection.value
        val url = s.url.trim()
        if (url.isBlank() || s.busy) return
        DownloadCenter.reset()
        val format = formatOverride.ifBlank {
            if (selector.isNotBlank() && selector.contains("audio")) "mp3" else "mp4"
        }
        DownloadService.start(
            ctx = appCtx,
            url = url,
            format = format,
            quality = selection.value.formats.firstOrNull { it.id == selector }?.let { fmt ->
                if (fmt.height > 0) "${fmt.height}p" else "best"
            } ?: "best",
            proxyMode = "",
            selector = selector,
        )
    }

    /** 仅音频：走 mp3 档位 */
    fun startAudioDownload() = startDownload(selector = "", formatOverride = "mp3")

    fun cancel() {
        engine.cancel()
        DownloadService.cancel(appCtx)
    }

    fun pasteFromClipboard() {
        val clipboard = appCtx.getSystemService(android.content.Context.CLIPBOARD_SERVICE)
            as ClipboardManager
        val text = clipboard.primaryClip?.getItemAt(0)?.text?.toString() ?: return
        val url = extractUrl(text)
        if (url.isNotBlank()) {
            selection.update { it.copy(url = url, fetchError = "") }
            fetch()
        }
    }

    private fun baseOptions(
        url: String,
        cfg: com.videodl.app.data.AppConfig,
    ): DownloadOptions = DownloadOptions(
        url = url,
        outputPath = "",
        proxyMode = cfg.proxyMode,
        proxyUrl = cfg.proxyUrl,
        cookieMode = cfg.cookieMode,
        cookiePath = cfg.cookiePathUri,
        format = cfg.defaultFormat,
        quality = cfg.defaultQuality,
        platform = Platform.detect(url),
        ffmpegLocation = com.videodl.app.data.FileRepository.ffmpegLocation(appCtx),
    )

    /** 与桌面版 extract_url_from_text 1:1 对应 */
    private fun extractUrl(text: String): String {
        val t = text.trim()
        if (t.startsWith("http")) return t.trimEnd('。', '．', '.', '，', ',', '/', '\\')
        Regex("https?://\\S+").find(t)?.let {
            return it.value.trimEnd('。', '．', '.', '，', ',', '/', '\\')
        }
        return ""
    }
}
