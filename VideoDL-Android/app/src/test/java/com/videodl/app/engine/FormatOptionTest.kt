package com.videodl.app.engine

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
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

    // ---- 真机实测踩到的坑：点中纯视频流会下到"没有声音的视频" ----
    @Test fun downloadSelector_videoOnly_必须自带音频() {
        val f = video(1080, "hvc1.1.6.L150", acodec = "none")
        val sel = f.downloadSelector
        assertTrue("纯视频流要拼上音频：$sel", sel.startsWith("30080+"))
        assertTrue("音频优先 AAC：$sel", sel.contains("bestaudio[acodec^=mp4a]"))
        assertTrue("要有兜底音频：$sel", sel.endsWith("/30080+bestaudio/30080"))
    }

    @Test fun downloadSelector_combinedFormat_unchanged() {
        // 音视频一体的流（如抖音常见）直接用，别画蛇添足
        val f = video(720, "avc1.640033", "mp4a.40.2")
        assertEquals("30080", f.downloadSelector)
    }

    @Test fun downloadSelector_audioOnly_unchanged() {
        val a = FormatOption(
            id = "30280", label = "仅音频", note = "", ext = "m4a",
            vcodec = "none", acodec = "mp4a", height = 0, fps = 0,
            sizeBytes = 0, tbr = 0.0, abr = 174.0, audioOnly = true,
        )
        assertEquals("30280", a.downloadSelector)
    }

    @Test fun editorFriendly_flagsIncompatibleCodecs() {
        assertTrue("H.264 应该友好", video(1080, "avc1.640033", "mp4a.40.2").editorFriendly)
        assertTrue("纯 H.264 视频流也友好（音频会拼 AAC）", video(1080, "avc1.640033").editorFriendly)
        assertEquals(false, video(1080, "hvc1.1.6.L150").editorFriendly)      // HEVC
        assertEquals(false, video(1080, "av01.0.08M.08").editorFriendly)      // AV1
    }

    @Test fun resolutionText_showsBothSides() {
        val vertical = video(1920, "avc1").copy(width = 1080)
        assertEquals("1080×1920", vertical.resolutionText)
        assertEquals("", video(1080, "avc1").resolutionText)   // width 未知时不瞎写
    }

    @Test fun qualityLabel_usesShortSideForVerticalVideo() {
        // 竖屏 1080×1920 应该叫 1080p（平台和用户的叫法），不是 1920p
        assertEquals("1080p", video(1920, "avc1").copy(width = 1080).qualityLabel)
        // 横屏不变
        assertEquals("1080p", video(1080, "avc1").copy(width = 1920).qualityLabel)
        // 音频画质
        val a = FormatOption(
            id = "30280", label = "仅音频", note = "", ext = "m4a",
            vcodec = "none", acodec = "mp4a", height = 0, fps = 0,
            sizeBytes = 0, tbr = 0.0, abr = 174.0, audioOnly = true,
        )
        assertEquals("audio", a.qualityLabel)
    }
}
