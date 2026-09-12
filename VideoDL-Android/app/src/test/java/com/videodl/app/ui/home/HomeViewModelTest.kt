package com.videodl.app.ui.home

import com.videodl.app.data.DownloadStatus
import com.videodl.app.data.VideoInfo
import com.videodl.app.engine.FormatOption
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class HomeUiStateTest {

    @Test fun initialState_isIdleAndEmpty() {
        val s = HomeUiState()
        assertEquals(DownloadStatus.Idle, s.status)
        assertEquals("", s.url)
        assertEquals("", s.fetchError)
        assertTrue(s.formats.isEmpty())
        assertEquals(null, s.info)
    }

    @Test fun busy_onlyWhileFetchingOrDownloading() {
        // 界面用它决定按钮是否禁用，别把 Done/Error 也算成"忙"
        assertTrue(HomeUiState(status = DownloadStatus.Fetching).busy)
        assertTrue(HomeUiState(status = DownloadStatus.Downloading).busy)
        assertEquals(false, HomeUiState(status = DownloadStatus.Idle).busy)
        assertEquals(false, HomeUiState(status = DownloadStatus.Done).busy)
        assertEquals(false, HomeUiState(status = DownloadStatus.Error).busy)
    }

    @Test fun fetchResult_carriesThumbnailAndFormats() {
        val info = VideoInfo("标题", "UP 主", 44, "1080x1920")
        val formats = listOf(
            FormatOption("30280", "仅音频", "", "m4a", "none", "mp4a", 0, 0, 0, 0.0, 174.0, true),
            FormatOption("30080", "1080p", "", "mp4", "avc1.640033", "none", 1080, 30, 0, 3378.0, 0.0, false),
        )
        val s = HomeUiState(
            url = "https://www.bilibili.com/video/BV1xZYU6eE9F",
            info = info,
            thumbnail = "https://i0.hdslb.com/bfs/archive/x.jpg",
            formats = formats,
        )
        assertEquals("1080x1920", s.info?.resolution)
        assertEquals(2, s.formats.size)
        assertTrue(s.thumbnail.isNotBlank())
        assertEquals(false, s.fetching)
    }

    @Test fun fetchError_surfacedForUi() {
        val s = HomeUiState(fetching = false, fetchError = "Unsupported URL")
        assertEquals("Unsupported URL", s.fetchError)
        assertEquals(false, s.fetching)
    }
}
