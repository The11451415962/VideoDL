package com.videodl.app.data

/**
 * 「这次要的是音频还是视频」的判定 + 音频产物用什么容器。
 *
 * 读侧（界面筛选）、写侧（命名、MIME、相册发布）共用这一份，避免各处各写一个 if
 * 而彼此对不上 —— 之前就是 `HomeViewModel` / `FileRepository` / `DownloadService`
 * 三处各判一次，判出三种结果，最后产出「扩展名 .mp3、内容却是 AAC」的文件。
 *
 * ## 为什么音频存 m4a 而不是 mp3
 *
 * yt-dlp 转 mp3 用的是 `libmp3lame` 编码器，而打包进 APK 的 `libffmpeg.so` 是
 * `--disable-gpl --disable-everything` 之后**只开了 mjpeg** 的精简包，
 * 一点编码能力都没有（详见 README「已知问题」）—— 选 mp3 只会得到一次失败。
 *
 * 而 m4a 不需要编码器：源音轨已经是 AAC 时，yt-dlp 走的是 `copy`（重新封装），
 * 只需要 mp4/ipod 封装器 + `aac_adtstoasc` 位流过滤器，这两样精简包里都有。
 * 所以配合 `-f "bestaudio[acodec^=mp4a]/bestaudio"` 优先挑 AAC 音轨，m4a 是真能出的。
 *
 * 等 ffmpeg 重建出 `libmp3lame` 之后，改这一个常量就能重新提供 mp3。
 */
object MediaTarget {
    const val AUDIO_EXT = "m4a"
    const val AUDIO_MIME = "audio/mp4"

    /**
     * format 或 quality 任一表示「要音频」。
     *
     * 保留 `"mp3"` 这个取值：老配置里可能存着它，不能因为改了容器就当视频处理。
     */
    fun isAudio(format: String, quality: String): Boolean =
        quality == "audio" || format == "mp3" || format == "m4a" || format == "audio"

    /** 实际落盘的扩展名 */
    fun ext(format: String, quality: String): String =
        if (isAudio(format, quality)) AUDIO_EXT else format.ifBlank { "mp4" }

    /** 发布到媒体库用的 MIME，必须和真实内容一致 */
    fun mime(format: String, quality: String): String = when {
        isAudio(format, quality) -> AUDIO_MIME
        format == "webm" -> "video/webm"
        else -> "video/mp4"
    }
}
