package com.videodl.app.ui.home

import android.app.Application
import android.content.ClipboardManager
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.videodl.app.data.MediaTarget
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
            // 新任务 begin() 后 finishedUri 为 null，不能再粘住上一次的文件
            finishedFile = dl.finishedUri,
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
        // 先在格式表里反查用户点的是哪一行（用它判断"这是不是一条纯音频流"）。
        // 画质标签用"短边"叫法（竖屏 1080×1920 显示为 1080p）。
        //
        // 用「精确 id 匹配」而不是 contains：id "1" 是 "137"/"31" 的子串，
        // contains 会误判成音频/别的格式。downloadSelector 可能是 "137+bestaudio/..."，
        // 所以按 + 、 / 拆开后精确比。
        val picked = s.formats.firstOrNull { fmt ->
            selector.isNotBlank() && selector.split('+', '/').any { it.trim() == fmt.id }
        }
        val audioPicked = picked?.audioOnly == true
        val format = formatOverride.ifBlank {
            // 旧版判的是 `selector.startsWith("bestaudio")`，但 downloadSelector 返回的是
            // 具体格式 id（如 "30280"），这个条件永远不成立 —— 于是选了音频却按 mp4 命名，
            // 又被 buildOutputPath 按 quality=="audio" 写成 .mp3，产出后缀与内容不符的文件。
            if (audioPicked || selector.startsWith("bestaudio")) MediaTarget.AUDIO_EXT else "mp4"
        }
        DownloadService.start(
            ctx = appCtx,
            url = url,
            format = format,
            // 音频任务没有"画质"可言，标签要显示成"仅音频"，否则会写成"最佳 · m4a"
            quality = if (MediaTarget.isAudio(format, "")) "audio"
            else (picked?.qualityLabel ?: "best"),
            proxyMode = "",
            selector = selector,
        )
    }

    /** 仅音频：走音频档位（产物是 m4a，见 [MediaTarget] 的说明） */
    fun startAudioDownload() = startDownload(selector = "", formatOverride = MediaTarget.AUDIO_EXT)

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
