package com.videodl.app.engine

import org.junit.Assert.*
import org.junit.Test

class FormatTest {
    @Test fun audio_returnsMp3() {
        assertEquals(listOf("-f", "bestaudio/best", "--audio-format", "mp3"),
            Format.resolve("mp4", "audio", "YouTube"))
    }
    @Test fun youtube_best_mp4() {
        // 2026-08-28 起 YouTube 改用 H.264(avc1) + AAC(mp4a)：手机相册/剪辑 App 通用性最好，
        // 因此不再按 ext=mp4 过滤，改为断言编解码器 + 合并容器。
        val joined = Format.resolve("mp4", "best", "YouTube").joinToString(" ")
        assertTrue(joined.contains("vcodec^=avc1"))
        assertTrue(joined.contains("acodec^=mp4a"))
        assertTrue(joined.contains("--merge-output-format mp4"))
    }
    @Test fun bilibili_noExtFilter() {
        val r = Format.resolve("mp4", "1080p", "Bilibili")
        assertFalse(r.joinToString().contains("ext="))
        assertTrue(r.joinToString().contains("height<=1080"))
    }
}
