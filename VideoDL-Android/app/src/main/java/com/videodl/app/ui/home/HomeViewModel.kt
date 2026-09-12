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
import com.videodl.app.service.DownloadService
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

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
    /** 完成后打开用的目标：相册是 content:// URI，未开相册时是文件路径 */
    val finishedFile: String? = null,
    val errorMessage: String = "",
    /** 来自设置页的「下载完成后自动打开文件」开关 */
    val autoOpenFile: Boolean = true,
    /** 人类可读的保存位置（"系统相册" 或某个目录） */
    val destination: String = "",
) {
    val busy: Boolean
        get() = status == DownloadStatus.Downloading || status == DownloadStatus.Fetching
}

/**
 * 主页只负责"选择"和"转发动作"；真正的下载在 [DownloadService] 里跑，
 * 状态从进程内的 [DownloadCenter] 读回来。这样切走 App 下载也不会断。
 */
class HomeViewModel(app: Application) : AndroidViewModel(app) {
    private val appCtx: Application = app
    private val configRepo: ConfigRepository = ConfigRepositoryImpl(app)

    /** 界面自己的选择状态（链接、格式、清晰度、代理） */
    private val selection = MutableStateFlow(HomeUiState())

    val state: StateFlow<HomeUiState> = combine(selection, DownloadCenter.state) { sel, dl ->
        sel.copy(
            percent = dl.percent,
            speed = dl.speed,
            eta = dl.eta,
            status = dl.status,
            logs = dl.logs,
            videoInfo = dl.info,
            finishedFile = dl.finishedUri,
            errorMessage = dl.error,
            destination = dl.destination,
        )
    }.stateIn(viewModelScope, SharingStarted.Eagerly, HomeUiState())

    init {
        viewModelScope.launch {
            configRepo.configFlow.collect { cfg ->
                selection.update {
                    it.copy(
                        proxyMode = cfg.proxyMode,
                        format = cfg.defaultFormat,
                        quality = cfg.defaultQuality,
                        autoOpenFile = cfg.autoOpenFile,
                    )
                }
            }
        }
    }

    fun onUrlChanged(url: String) = selection.update { it.copy(url = url) }
    fun onFormatChanged(fmt: String) = selection.update { it.copy(format = fmt) }
    fun onQualityChanged(q: String) = selection.update { it.copy(quality = q) }
    fun onProxyModeChanged(p: String) = selection.update { it.copy(proxyMode = p) }

    /**
     * 系统分享直达。
     *
     * @param startNow 由 [com.videodl.app.ShareReceiver] 分享过来时它是 true —— 下载
     *   已经在分享入口直接启动了，这里只回填链接，避免重复下一次；
     *   其它入口（例如直接把 SEND 发给界面）才由这里启动。
     */
    fun consumeSharedUrl(url: String, startNow: Boolean = true) {
        if (url.isBlank()) return
        selection.update { it.copy(url = url) }
        if (startNow && !state.value.busy) startDownload()
    }

    fun startDownload() {
        val s = selection.value
        if (s.url.isBlank() || s.busy) return
        DownloadCenter.reset()
        DownloadService.start(appCtx, s.url.trim(), s.format, s.quality, s.proxyMode)
    }

    fun cancel() {
        // 与 Service 同进程：先让引擎停下，Service 收到取消结果后会收尾并停掉通知
        (appCtx as MainApplication).engine.cancel()
        DownloadService.cancel(appCtx)
    }

    fun pasteFromClipboard() {
        val clipboard = appCtx.getSystemService(android.content.Context.CLIPBOARD_SERVICE)
            as ClipboardManager
        val text = clipboard.primaryClip?.getItemAt(0)?.text?.toString() ?: return
        val url = extractUrl(text)
        if (url.isNotBlank()) selection.update { it.copy(url = url) }
    }

    /** 与桌面版 _extract_url_from_text 1:1 对应 */
    private fun extractUrl(text: String): String {
        val t = text.trim()
        if (t.startsWith("http")) return t.trimEnd('。', '．', '.', '，', ',', '/', '\\')
        Regex("https?://\\S+").find(t)?.let {
            return it.value.trimEnd('。', '．', '.', '，', ',', '/', '\\')
        }
        return ""
    }
}
