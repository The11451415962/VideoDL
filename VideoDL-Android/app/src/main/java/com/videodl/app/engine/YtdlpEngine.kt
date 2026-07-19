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
