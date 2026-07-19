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

class ProxyResolverTest {
    @Test fun direct_returnsNull() {
        assertNull(ProxyResolver.resolve("direct", "http://127.0.0.1:7897", "https://youtube.com/v"))
    }
    @Test fun proxy_alwaysReturnsUrl() {
        assertEquals("http://127.0.0.1:7897",
            ProxyResolver.resolve("proxy", "http://127.0.0.1:7897", "https://bilibili.com/v"))
    }
    @Test fun auto_youtubeReturnsUrl_bilibiliReturnsNull() {
        assertEquals("http://127.0.0.1:7897",
            ProxyResolver.resolve("auto", "http://127.0.0.1:7897", "https://youtube.com/v"))
        assertNull(ProxyResolver.resolve("auto", "http://127.0.0.1:7897", "https://bilibili.com/v"))
    }
}
