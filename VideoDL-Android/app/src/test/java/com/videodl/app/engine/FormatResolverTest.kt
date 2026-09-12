package com.videodl.app.engine

import org.junit.Assert.*
import org.junit.Test

class PlatformTest {
    @Test fun youtube() {
        assertEquals("YouTube", Platform.detect("https://www.youtube.com/watch?v=abc"))
        assertEquals("YouTube", Platform.detect("https://youtu.be/abc"))
    }
    @Test fun bilibili() {
        assertEquals("Bilibili", Platform.detect("https://www.bilibili.com/video/BV123"))
        assertEquals("Bilibili", Platform.detect("https://b23.tv/xyz"))
    }
    @Test fun douyin() {
        assertEquals("抖音", Platform.detect("https://v.douyin.com/abc"))
        assertEquals("抖音", Platform.detect("https://www.tiktok.com/@x/video/1"))
    }
    @Test fun unknown() {
        assertEquals("未知", Platform.detect("https://example.com/v"))
    }
}

/**
 * 代理决策的完整真值表。
 *
 * 这些用例以前测的是 `ProxyResolver` 里那份**从未被调用**的简单实现，而线上跑的是
 * YtdlpEngineImpl 里的另一份，两边语义早就漂开了（测试说 auto 只给 YouTube 走代理，
 * 实际跑的是"地址通就全都走代理"）。现在决策只有一份纯函数，测试直接覆盖它。
 */
class ProxyResolverTest {
    private val url = "http://127.0.0.1:7897"

    @Test fun direct_alwaysDirect() {
        assertNull(ProxyResolver.resolve("direct", url, "YouTube", proxyReachable = true).proxyUrl)
    }

    @Test fun vpn_winsOverEverything() {
        // 有 VPN 隧道就直连，让隧道自己路由，别套两层
        for (mode in listOf("auto", "proxy", "direct")) {
            val d = ProxyResolver.resolve(mode, url, "YouTube", vpnActive = true, proxyReachable = true)
            assertNull("mode=$mode 时 VPN 应直连", d.proxyUrl)
            assertTrue("应说明是因为 VPN", d.note.contains("VPN"))
        }
    }

    @Test fun forcedProxy_usesUrlWhenReachable() {
        assertEquals(url, ProxyResolver.resolve("proxy", url, "Bilibili", proxyReachable = true).proxyUrl)
    }

    @Test fun forcedProxy_fallsBackToDirectWhenUnreachable_andSaysWhy() {
        // 回退直连可以，但不能静默：必须告诉用户为什么没用上代理
        val d = ProxyResolver.resolve("proxy", url, "YouTube", proxyReachable = false)
        assertNull(d.proxyUrl)
        assertTrue("要说清原因，实际 note=${d.note}", d.note.contains("连不上"))
    }

    @Test fun forcedProxy_blankUrlFallsBackToDirect() {
        val d = ProxyResolver.resolve("proxy", "   ", "YouTube", proxyReachable = true)
        assertNull(d.proxyUrl)
        assertTrue("要说清是没填地址，实际 note=${d.note}", d.note.contains("没填地址"))
    }

    @Test fun auto_onlyYoutubeGoesThroughProxy() {
        // B 站/抖音走境外节点反而更慢甚至被拒，auto 只给 YouTube 走
        assertEquals(url, ProxyResolver.resolve("auto", url, "YouTube", proxyReachable = true).proxyUrl)
        assertNull(ProxyResolver.resolve("auto", url, "Bilibili", proxyReachable = true).proxyUrl)
        assertNull(ProxyResolver.resolve("auto", url, "抖音", proxyReachable = true).proxyUrl)
        assertNull(ProxyResolver.resolve("auto", url, "未知", proxyReachable = true).proxyUrl)
    }

    @Test fun auto_unreachableGoesDirect() {
        assertNull(ProxyResolver.resolve("auto", url, "YouTube", proxyReachable = false).proxyUrl)
    }
}
