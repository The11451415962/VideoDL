package com.videodl.app.engine

import java.io.File
import kotlinx.coroutines.flow.Flow

sealed class DownloadEvent {
    object Started : DownloadEvent()
    data class Info(
        val title: String, val uploader: String,
        val duration: Int, val resolution: String,
        val thumbnail: String = "",
    ) : DownloadEvent()
    data class Progress(val percent: Float, val speed: String, val eta: String) : DownloadEvent()
    data class Log(val line: String) : DownloadEvent()
    data class Finished(val filePath: String) : DownloadEvent()
    data class Error(val message: String) : DownloadEvent()

    /** 用户主动取消。和 [Error] 分开，否则「点了停止」会被报成「下载失败」。 */
    object Cancelled : DownloadEvent()
}

/** 抓取结果的完整信息：结果卡片（缩略图/标题/时长）+ 格式弹窗都用它 */
data class MediaDetail(
    val title: String,
    val uploader: String,
    val duration: Int,
    val thumbnail: String,
    val formats: List<FormatOption>,
)

interface YtdlpEngine {
    fun fetchInfo(url: String, options: DownloadOptions): DownloadEvent.Info

    /** 抓取详情：标题/上传者/时长/缩略图 + 可选格式（结果卡片与格式弹窗的数据源） */
    fun fetchDetail(url: String, options: DownloadOptions): MediaDetail

    fun download(options: DownloadOptions): Flow<DownloadEvent>
    fun cancel()

    /**
     * 让产物在手机相册 / 剪映里**能被编辑**：用 MediaCodec 把视频流重编一遍。
     *
     * 平台给的原始 H.264 流会被 ColorOS 编辑器和剪映拒绝（能播不能编），
     * 只有重新编码过的视频流才认 —— 详见 [VideoTranscoder] 里的对照实验表。
     *
     * 成功返回新文件（调用方负责替换/发布），失败返回 null（保留原文件）。
     * 内部阻塞，必须在后台线程调用。
     */
    fun makeEditorFriendly(src: File, ffmpegLocation: String): File?
}
