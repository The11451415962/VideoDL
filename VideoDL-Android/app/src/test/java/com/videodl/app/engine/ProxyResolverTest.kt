package com.videodl.app.engine

import org.junit.Assert.*
import org.junit.Test

class FormatTest {
    @Test fun audio_returnsMp3() {
        assertEquals(listOf("-f", "bestaudio/best", "--audio-format", "mp3"),
            Format.resolve("mp4", "audio", "YouTube"))
    }
    @Test fun youtube_best_mp4() {
        val r = Format.resolve("mp4", "best", "YouTube")
        assertTrue(r.joinToString().contains("[ext=mp4]"))
        assertTrue(r.joinToString().contains("--merge-output-format"))
    }
    @Test fun bilibili_noExtFilter() {
        val r = Format.resolve("mp4", "1080p", "Bilibili")
        assertFalse(r.joinToString().contains("ext="))
        assertTrue(r.joinToString().contains("height<=1080"))
    }
}
