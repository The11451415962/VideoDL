package com.videodl.app.engine

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
}
