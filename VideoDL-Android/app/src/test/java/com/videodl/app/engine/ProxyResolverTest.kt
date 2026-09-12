package com.videodl.app.engine

import org.junit.Assert.*
import org.junit.Test

class FormatTest {
    @Test fun audio_returnsMp3() {
        assertEquals(listOf("-f", "bestaudio/best", "--audio-format", "mp3"),
            Format.resolve("mp4", "audio", "YouTube"))
    }

    @Test fun mp4_首要条件必须是编码而不是容器() {
        // 回归测试：坏在"选了 MP4 却下到 AV1"。
        // 旧版 YouTube 用 [ext=mp4] 过滤，而 YouTube/B站的 AV1 流同样是 mp4 容器，
        // 于是首选条件形同虚设，剪映直接报不支持。所以第一顺位必须是 vcodec=avc1 + acodec=mp4a。
        for (platform in listOf("YouTube", "Bilibili", "抖音", "未知")) {
            val first = Format.resolve("mp4", "best", platform)[1].split("/").first()
            assertTrue("$platform 首选视频应为 avc1：$first", first.contains("vcodec^=avc1"))
            assertTrue("$platform 首选音频应为 mp4a：$first", first.contains("acodec^=mp4a"))
        }
    }

    @Test fun mp4_逐级回退且仍合并成mp4() {
        val args = Format.resolve("mp4", "1080p", "Bilibili")
        val selector = args[1]
        assertTrue("要带清晰度上限", selector.contains("height<=1080"))
        assertTrue("必须有兜底层级，否则找不到 avc1 时会直接失败", selector.split("/").size >= 4)
        assertTrue(args.contains("--merge-output-format"))
        assertEquals("mp4", args.last())
    }

    @Test fun webm_仍按webm合并() {
        val args = Format.resolve("webm", "720p", "YouTube")
        assertTrue(args[1].contains("[ext=webm]"))
        assertEquals("webm", args.last())
    }
}
