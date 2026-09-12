package com.videodl.app.engine

import org.junit.Assert.assertEquals
import org.junit.Test

/** 格式卡片的展示文本（体积/编码/码率）—— 纯逻辑，无需设备 */
class FormatOptionTest {

    private fun video(height: Int, vcodec: String, acodec: String = "none",
                      size: Long = 0, tbr: Double = 0.0, fps: Int = 30) = FormatOption(
        id = "30080", label = "${height}p", note = "", ext = "mp4",
        vcodec = vcodec, acodec = acodec, height = height, fps = fps,
        sizeBytes = size, tbr = tbr, abr = 0.0, audioOnly = false,
    )

    @Test fun sizeText_formatsUnits() {
        assertEquals("", FormatOption.formatBytes(0))
        assertEquals("512 B", FormatOption.formatBytes(512))
        assertEquals("1.0 KB", FormatOption.formatBytes(1024))
        assertEquals("12.3 MB", FormatOption.formatBytes((12.3 * 1024 * 1024).toLong()))
        assertEquals("1.5 GB", FormatOption.formatBytes((1.5 * 1024 * 1024 * 1024).toLong()))
    }

    @Test fun codecText_stripsProfileSuffixAndHidesNone() {
        // yt-dlp 给的是 "avc1.640033" 这种带 profile 的串，界面上只要 "avc1"
        val both = video(1080, "avc1.640033", "mp4a.40.2")
        assertEquals("avc1 · mp4a", both.codecText)

        val videoOnly = video(1080, "av01.0.08M.08")
        assertEquals("av01", videoOnly.codecText)

        val none = video(1080, "none", "none")
        assertEquals("", none.codecText)
    }

    @Test fun bitrateText_usesAbrForAudioOnly() {
        assertEquals("3378k", video(1080, "avc1", tbr = 3378.4).bitrateText)
        val audio = FormatOption(
            id = "30280", label = "仅音频", note = "", ext = "m4a",
            vcodec = "none", acodec = "mp4a", height = 0, fps = 0,
            sizeBytes = 0, tbr = 174.0, abr = 174.2, audioOnly = true,
        )
        assertEquals("174k", audio.bitrateText)   // 音频用 abr，不用 tbr
    }

    @Test fun bitrateText_emptyWhenUnknown() {
        assertEquals("", video(1080, "avc1", tbr = 0.0).bitrateText)
    }
}
