package com.videodl.app.service

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 通知栏进度文字（纯函数）。
 * 队列数量必须出现在通知里 —— 用户切走 App 后靠它知道"后面还排着几个"。
 */
class ProgressTextTest {

    @Test fun basicPercentOnly() {
        assertEquals("0%", progressText(0f, "", ""))
        assertEquals("47%", progressText(47.6f, "", ""))
    }

    @Test fun includesSpeedAndEta() {
        assertEquals("47%  ·  ↓1.3MiB/s  ·  剩余 00:12", progressText(47.2f, "1.3MiB/s", "00:12"))
    }

    @Test fun includesQueueCountWhenQueued() {
        val text = progressText(12f, "800KiB/s", "00:30", queued = 2)
        assertTrue("应显示队列数量：$text", text.endsWith("队列 2"))
    }

    @Test fun noQueueSuffixWhenEmpty() {
        val text = progressText(12f, "", "", queued = 0)
        assertEquals("12%", text)
    }
}
