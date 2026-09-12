package com.videodl.app.ui.home

import com.videodl.app.engine.FormatOption
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 格式弹窗的排序/分组逻辑（纯函数，无需设备）。
 * 用真实的 B 站格式数据当样本：同一分辨率下 avc1/hvc1/av01 三种编码。
 */
class SplitFormatsTest {

    private fun fmt(
        id: String, height: Int, vcodec: String, acodec: String = "none",
        ext: String = "mp4", tbr: Double = 0.0, audioOnly: Boolean = false,
    ) = FormatOption(
        id = id, label = if (audioOnly) "仅音频" else "${height}p", note = "", ext = ext,
        vcodec = vcodec, acodec = acodec, height = height, fps = 30,
        sizeBytes = 0, tbr = tbr, abr = 0.0, audioOnly = audioOnly,
    )

    private val sample = listOf(
        fmt("30280", 0, "none", "mp4a", "m4a", audioOnly = true),
        fmt("30016", 360, "avc1.640033", tbr = 557.0),
        fmt("30011", 360, "hvc1.1.6.L120", tbr = 229.0),
        fmt("100022", 360, "av01.0.08M.08", tbr = 218.0),
        fmt("30080", 1080, "avc1.640033", tbr = 3378.0),
        fmt("30077", 1080, "hvc1.1.6.L150", tbr = 1112.0),
        fmt("100026", 1080, "av01.0.08M.08", tbr = 1074.0),
    )

    @Test fun videoFormats_sortedByHeightDescending() {
        val (video, _) = splitFormats(sample)
        val heights = video.map { it.height }
        assertEquals(heights.sortedDescending(), heights)
        assertEquals(1080, heights.first())
    }

    @Test fun sameHeight_keepsOnlyOnePerCodecFamily() {
        val (video, _) = splitFormats(sample)
        // 1080p 下 avc1 / hvc1 / av01 是三种编码，应该都保留（用户要能选 H.264）
        val at1080 = video.filter { it.height == 1080 }.map { it.vcodec.substringBefore('.') }
        assertTrue("应保留多编码候选：$at1080", at1080.contains("avc1"))
        assertTrue(at1080.contains("av01"))
        assertTrue(at1080.size >= 2)
    }

    @Test fun audioFormats_separatedIntoOwnGroup() {
        val (video, audio) = splitFormats(sample)
        assertEquals(1, audio.size)
        assertEquals("30280", audio[0].id)
        assertTrue("音频不该混进视频组", video.none { it.audioOnly })
    }

    @Test fun junkFormats_areFilteredOut() {
        val junk = listOf(
            fmt("", 0, "none", "none"),                    // 无 id
            fmt("sb0", 0, "none", "none"),                 // storyboard：视频音频都没有
            fmt("30080", 1080, "avc1.640033"),
        )
        val (video, audio) = splitFormats(junk)
        assertEquals(1, video.size)
        assertEquals("30080", video[0].id)
        assertTrue(audio.isEmpty())
    }

    @Test fun sameHeight_prefersH264First() {
        // 弹窗第一行应该是 H.264 —— 用户随便点第一个也大概率拿到剪映能用的格式
        val (video, _) = splitFormats(sample)
        val top = video.first()
        assertEquals("avc1", top.vcodec.substringBefore('.'))
        assertEquals(1080, top.height)
    }

    @Test fun audio_prefersAacFirst() {
        val mixed = listOf(
            fmt("30280", 0, "none", "mp4a", "m4a", audioOnly = true),
            fmt("30250", 0, "none", "opus", "webm", audioOnly = true),
        )
        val (_, audio) = splitFormats(mixed)
        assertEquals("30280", audio.first().id)
    }

    @Test fun emptyInput_returnsEmptyGroups() {
        val (video, audio) = splitFormats(emptyList())
        assertTrue(video.isEmpty())
        assertTrue(audio.isEmpty())
    }
}
