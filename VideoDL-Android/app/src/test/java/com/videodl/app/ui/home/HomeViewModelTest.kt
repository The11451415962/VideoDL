package com.videodl.app.ui.home

import org.junit.Assert.assertEquals
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
}
