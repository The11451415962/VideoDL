package com.videodl.app.data

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class ConfigRepositoryTest {
    @Test
    fun defaultValues_areCorrect() = runBlocking {
        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
        val repo = ConfigRepositoryImpl(ctx)
        val cfg = repo.configFlow.first()
        assertEquals("auto", cfg.proxyMode)
        assertEquals("http://127.0.0.1:7897", cfg.proxyUrl)
        assertEquals("none", cfg.cookieMode)
        assertEquals("mp4", cfg.defaultFormat)
        assertEquals("best", cfg.defaultQuality)
        assertEquals(true, cfg.autoOpenFile)
    }

    @Test
    fun update_persistsChange() = runBlocking {
        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
        val repo = ConfigRepositoryImpl(ctx)
        repo.update { it.copy(proxyMode = "proxy", defaultFormat = "mp3") }
        val cfg = repo.configFlow.first()
        assertEquals("proxy", cfg.proxyMode)
        assertEquals("mp3", cfg.defaultFormat)
    }
}
