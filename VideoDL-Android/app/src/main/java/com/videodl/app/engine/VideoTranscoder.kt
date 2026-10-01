package com.videodl.app.engine

import android.media.MediaCodec
import android.media.MediaCodecInfo
import android.media.MediaExtractor
import android.media.MediaFormat
import android.media.MediaMuxer
import android.util.Log
import java.io.File

/**
 * 用系统自带的 MediaCodec 把视频流重新编码一遍（音频由调用方原样搬运）。
 *
 * ## 为什么要这么做
 *
 * 真机实测（2026-09-13，PJC110 / Android 15）：下载到的视频（YouTube/抖音这类平台给的
 * 原始 H.264 流，被 yt-dlp 用 `-c copy` 封装进 MP4）**在 ColorOS 相册和剪映里能正常播放，
 * 但一点「编辑」就报「格式不支持」**。
 *
 * 做过的对照实验（同一段视频，每次只改一个变量）：
 *
 * | 改动 | 结果 |
 * |---|---|
 * | 原始文件 | ❌ |
 * | 只补容器里的 `colr` 色彩盒子 | ❌ |
 * | 只往 SPS 里注入 VUI 色彩信息 | ❌ |
 * | 改文件名（去 `#`、去前导符号） | ❌ |
 * | **只重新编码视频流**（音频原样 copy） | **✅ 能编辑** |
 * | 只重新编码音频流（视频原样 copy） | ❌ |
 *
 * 两个文件的编码参数（profile/level/分辨率/帧率/像素格式）和 SPS 字段几乎完全一致，
 * 所以差异在码流内部 —— **编辑器就是要吃"重新编过"的视频流**。
 *
 * ## 为什么用 MediaCodec 而不是 ffmpeg
 *
 * - 打进 APK 的 ffmpeg **没有编码器**（`--disable-everything` 后只留了 mjpeg）
 * - `libx264` 是 **GPL**，会把整个项目传染成 GPL（本项目要闭源发布）
 * - `h264_mediacodec` 在 ffmpeg 里**用不了**：ffmpeg 是以独立进程被调起的，没有 JVM，
 *   拿不到 MediaCodec
 * - MediaCodec 是系统 API：**硬件编码、快、无许可问题**
 *
 * ## 实现轮廓
 *
 * 解码器直接输出到编码器的输入 Surface（零拷贝，全程 GPU 内存），编码成 H.264 写进一个
 * **只含视频轨**的临时 MP4。随后由调用方用打包的 ffmpeg 把「重编的视频 + 原始音频」
 * 重新封装到一起，顺带补 `colr`/faststart —— 这样音频既不用解码也不用重编，快且无损。
 */
object VideoTranscoder {

    private const val TAG = "VideoDL"
    private const val TIMEOUT_US = 10_000L
    /** 关键帧间隔（秒）。调小一点，编辑器拖时间轴更顺。 */
    private const val I_FRAME_INTERVAL = 1
    private const val TARGET_BITRATE = 8_000_000
    /** 兜底上限，防止编解码器卡住时死循环。 */
    private const val MAX_LOOPS = 200_000

    /**
     * @param ok 成功与否
     * @param videoOnly 成功时指向只含视频轨的临时文件（调用方负责搬运/删除）
     * @param frames 编出的帧数（排查用）
     * @param reason 失败原因（给日志看）
     */
    data class Result(val ok: Boolean, val videoOnly: File?, val frames: Int = 0, val reason: String = "")

    /**
     * 把 [src] 的视频流重编成 H.264，写到 [dst]（只含视频轨）。
     *
     * 内部阻塞，必须在后台线程调用。
     */
    fun transcodeVideo(src: File, dst: File): Result {
        val extractor = MediaExtractor()
        var decoder: MediaCodec? = null
        var encoder: MediaCodec? = null
        var muxer: MediaMuxer? = null
        try {
            extractor.setDataSource(src.absolutePath)
            val vIndex = (0 until extractor.trackCount).firstOrNull { i ->
                extractor.getTrackFormat(i).getString(MediaFormat.KEY_MIME)
                    ?.startsWith("video/") == true
            } ?: return Result(false, null, reason = "文件里没有视频轨")

            val srcFormat = extractor.getTrackFormat(vIndex)
            val srcMime = srcFormat.getString(MediaFormat.KEY_MIME)
                ?: return Result(false, null, reason = "读不到编码格式")
            val width = srcFormat.getIntOr(MediaFormat.KEY_WIDTH, 0)
            val height = srcFormat.getIntOr(MediaFormat.KEY_HEIGHT, 0)
            if (width <= 0 || height <= 0) return Result(false, null, reason = "读不到分辨率")
            val fps = srcFormat.getIntOr(MediaFormat.KEY_FRAME_RATE, 30).coerceIn(1, 120)
            // 源上的旋转信息要带过去，否则竖屏素材会被摆正
            val rotation = srcFormat.getIntOr(MediaFormat.KEY_ROTATION, 0)

            Log.d(TAG, "transcode: ${src.name} ${width}x$height ${fps}fps $srcMime rot=$rotation -> video/avc")

            encoder = MediaCodec.createEncoderByType(MediaFormat.MIMETYPE_VIDEO_AVC)
            val encFormat = MediaFormat.createVideoFormat(
                MediaFormat.MIMETYPE_VIDEO_AVC, width, height,
            ).apply {
                setInteger(
                    MediaFormat.KEY_COLOR_FORMAT,
                    MediaCodecInfo.CodecCapabilities.COLOR_FormatSurface,
                )
                setInteger(MediaFormat.KEY_BIT_RATE, TARGET_BITRATE)
                setInteger(MediaFormat.KEY_FRAME_RATE, fps)
                setInteger(MediaFormat.KEY_I_FRAME_INTERVAL, I_FRAME_INTERVAL)
            }
            encoder.configure(encFormat, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE)
            val inputSurface = encoder.createInputSurface()
            encoder.start()

            decoder = MediaCodec.createDecoderByType(srcMime)
            decoder.configure(srcFormat, inputSurface, null, 0)
            decoder.start()

            muxer = MediaMuxer(dst.absolutePath, MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4)

            extractor.selectTrack(vIndex)
            val info = MediaCodec.BufferInfo()
            var videoTrack = -1
            var muxerStarted = false
            var inputDone = false
            var outputDone = false
            var frames = 0
            var loops = 0

            while (!outputDone && loops++ < MAX_LOOPS) {
                // ---- 1) 把源视频样本喂给解码器 ----
                if (!inputDone) {
                    val inIdx = decoder.dequeueInputBuffer(TIMEOUT_US)
                    if (inIdx >= 0) {
                        val inBuf = decoder.getInputBuffer(inIdx)!!
                        val size = extractor.readSampleData(inBuf, 0)
                        if (size < 0) {
                            decoder.queueInputBuffer(
                                inIdx, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM,
                            )
                            inputDone = true
                        } else {
                            decoder.queueInputBuffer(inIdx, 0, size, extractor.sampleTime, 0)
                            extractor.advance()
                        }
                    }
                }

                // ---- 2) 解码结果直接渲染到编码器的输入 Surface（零拷贝）----
                val decIdx = decoder.dequeueOutputBuffer(info, TIMEOUT_US)
                if (decIdx >= 0) {
                    val decEos = info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0
                    // Surface 模式下 buffer 是 null，第二个参数 = true 即"把这一帧渲染出去"
                    decoder.releaseOutputBuffer(decIdx, true)
                    if (decEos) {
                        // 没有更多帧了 → 让编码器收尾
                        encoder.signalEndOfInputStream()
                    }
                }

                // ---- 3) 取编码结果，写进只有视频轨的 mp4 ----
                val encIdx = encoder.dequeueOutputBuffer(info, TIMEOUT_US)
                if (encIdx == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED) {
                    if (!muxerStarted) {
                        val trackFormat = encoder.outputFormat
                        if (rotation != 0) {
                            runCatching { trackFormat.setInteger(MediaFormat.KEY_ROTATION, rotation) }
                        }
                        videoTrack = muxer.addTrack(trackFormat)
                        muxer.start()
                        muxerStarted = true
                    }
                } else if (encIdx >= 0) {
                    val outBuf = encoder.getOutputBuffer(encIdx)
                    val isConfig = info.flags and MediaCodec.BUFFER_FLAG_CODEC_CONFIG != 0
                    if (outBuf != null && info.size > 0 && !isConfig && muxerStarted) {
                        outBuf.position(info.offset)
                        outBuf.limit(info.offset + info.size)
                        muxer.writeSampleData(videoTrack, outBuf, info)
                        frames++
                    }
                    val encEos = info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0
                    encoder.releaseOutputBuffer(encIdx, false)
                    if (encEos) outputDone = true
                }
            }

            if (frames == 0) return Result(false, null, reason = "没有编出任何帧")
            if (loops >= MAX_LOOPS) return Result(false, null, frames, "超出循环上限，疑似卡死")
            return Result(true, dst, frames)

        } catch (e: Exception) {
            Log.e(TAG, "transcode failed", e)
            return Result(false, null, reason = e.message ?: e.javaClass.simpleName)
        } finally {
            runCatching { decoder?.stop() }
            runCatching { decoder?.release() }
            runCatching { encoder?.stop() }
            runCatching { encoder?.release() }
            runCatching { if (muxer != null) muxer.stop() }
            runCatching { muxer?.release() }
            runCatching { extractor.release() }
        }
    }

    private fun MediaFormat.getIntOr(key: String, def: Int): Int =
        if (containsKey(key)) runCatching { getInteger(key) }.getOrDefault(def) else def
}
