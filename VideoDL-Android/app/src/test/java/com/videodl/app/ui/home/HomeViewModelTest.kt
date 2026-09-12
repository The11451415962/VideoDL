package com.videodl.app.ui.home

import com.videodl.app.data.DownloadStatus
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class HomeViewModelPureTest {
    @Test fun formatChanged_updatesState() {
        val s = HomeUiState()
        val next = s.copy(format = "mp3")
        assertEquals("mp3", next.format)
    }

    @Test fun initialState_isIdle() {
        val s = HomeUiState()
        assertEquals(DownloadStatus.Idle, s.status)
        assertEquals("", s.url)
    }

    @Test fun busy_onlyWhileFetchingOrDownloading() {
        // 界面用它来决定按钮禁用，别把 Done/Error 也当成"忙"
        assertTrue(HomeUiState(status = DownloadStatus.Fetching).busy)
        assertTrue(HomeUiState(status = DownloadStatus.Downloading).busy)
        assertEquals(false, HomeUiState(status = DownloadStatus.Idle).busy)
        assertEquals(false, HomeUiState(status = DownloadStatus.Done).busy)
        assertEquals(false, HomeUiState(status = DownloadStatus.Error).busy)
    }
}
