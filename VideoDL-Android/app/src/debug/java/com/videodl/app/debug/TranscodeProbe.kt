package com.videodl.app.debug

import android.app.Activity
import android.os.Bundle
import android.util.Log
import com.videodl.app.MainApplication
import com.videodl.app.data.FileRepository
import java.io.File

/**
 * **只存在于 debug 包**的验证入口。
 *
 * 目的：验证「MediaCodec 重编视频 + 原始音频搬运」之后，手机相册/剪映是不是真的认这个文件。
 * 之前的验证全靠点相册里的「编辑」按钮，而那个自绘 UI 没法可靠地用 adb 操作（我点错过好几次），
 * 所以干脆给一个确定的入口：
 *
 * ```
 * adb push in.mp4 /sdcard/Android/data/com.videodl.app/files/probe_in.mp4
 * adb shell am start -a com.videodl.app.TRANSCODE_PROBE -n com.videodl.app/.debug.TranscodeProbe \
 *     --es name probe_in.mp4
 * ```
 *
 * 处理完会把结果发布到相册（`Movies/VideoDL/<名字>.edit.mp4`），日志走 logcat（tag=VideoDL）。
 */
class TranscodeProbe : Activity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val name = intent?.getStringExtra("name") ?: "probe_in.mp4"
        val app = application as MainApplication

        Thread {
            try {
                val src = File(getExternalFilesDir(null), name)
                Log.d(TAG, "probe: 输入 ${src.absolutePath} 存在=${src.isFile} " +
                    "大小=${if (src.isFile) src.length() else -1}")

                if (!src.isFile) {
                    Log.e(TAG, "probe: 输入文件不存在")
                    return@Thread
                }
                val ffmpeg = FileRepository.ffmpegLocation(this)
                val t0 = System.currentTimeMillis()
                val out = app.engine.makeEditorFriendly(src, ffmpeg)
                val cost = System.currentTimeMillis() - t0
                if (out == null) {
                    Log.e(TAG, "probe: 转码失败（${cost}ms）")
                    return@Thread
                }
                Log.d(TAG, "probe: 转码成功 ${out.absolutePath} ${out.length()} 字节 用时 ${cost}ms")

                val uri = FileRepository.publishToGallery(this, out, "video/mp4", false)
                Log.d(TAG, "probe: 发布到相册 -> $uri")
            } catch (e: Exception) {
                Log.e(TAG, "probe: 异常", e)
            } finally {
                runCatching { finish() }
            }
        }.start()
    }

    private companion object {
        const val TAG = "VideoDL"
    }
}
