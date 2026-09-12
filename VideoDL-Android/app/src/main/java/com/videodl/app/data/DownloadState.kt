package com.videodl.app.data

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

/** 视频基本信息（抓取自 yt-dlp） */
data class VideoInfo(
    val title: String,
    val uploader: String,
    val duration: Int,
    val resolution: String,
)

enum class DownloadStatus { Idle, Fetching, Downloading, Done, Error }

/**
 * 一次下载的实时快照。
 *
 * 下载跑在前台 Service 里（切走 App、锁屏都不中断），界面只读这个快照；
 * 两者都在同一个进程内，所以用单例状态流传递，不需要 AIDL/Binder。
 */
data class DownloadSnapshot(
    val status: DownloadStatus = DownloadStatus.Idle,
    val percent: Float = 0f,
    val speed: String = "",
    val eta: String = "",
    val logs: List<String> = emptyList(),
    val info: VideoInfo? = null,
    /** 完成后用于打开的文件：相册是 content:// URI，未开相册时是文件路径 */
    val finishedUri: String? = null,
    val finishedDisplayName: String = "",
    val error: String = "",
    /** 人类可读的保存位置说明，直接显示给用户 */
    val destination: String = "",
)

/** 下载状态总线：Service 写，界面读。 */
object DownloadCenter {

    private val _state = MutableStateFlow(DownloadSnapshot())
    val state: StateFlow<DownloadSnapshot> = _state.asStateFlow()

    private const val MAX_LOGS = 200

    fun reset() {
        _state.value = DownloadSnapshot()
    }

    fun begin() {
        _state.value = DownloadSnapshot(status = DownloadStatus.Fetching)
    }

    fun update(transform: (DownloadSnapshot) -> DownloadSnapshot) {
        _state.update(transform)
    }

    fun log(line: String) {
        _state.update { it.copy(logs = (it.logs + line).takeLast(MAX_LOGS)) }
    }

    fun note(text: String) {
        log(text)
    }
}
