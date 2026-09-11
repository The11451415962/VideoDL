package com.videodl.app.data

import org.junit.Assert.*
import org.junit.Test
import java.io.File

class NamingTest {
    @Test fun firstAvailable_noSuffix() {
        assertEquals("/dl/title.mp4", Naming.nextFilePath("/dl", "title", "mp4"))
    }
    @Test fun conflict_addsSuffix() {
        val existing = setOf("title.mp4", "title(2).mp4")
        assertEquals("/dl/title(3).mp4", Naming.nextFilePath("/dl", "title", "mp4", existing))
    }
    @Test fun sanitize_replacesForbiddenChars() {
        assertEquals("a_b_c_d", Naming.sanitize("a/b\\c:d"))
        assertEquals("clean title", Naming.sanitize("clean title"))
    }
}

class FileRepositoryPureTest {
    @Test fun buildOutputPath_firstNoSuffix() {
        val dir = createTempDir().absolutePath
        assertEquals("$dir/视频.mp4", FileRepository.buildOutputPath(dir, "视频", "mp4", "best"))
    }
    @Test fun buildOutputPath_conflictAddsSuffix() {
        val dir = createTempDir()
        dir.resolve("title.mp4").createNewFile()
        assertEquals("${dir.absolutePath}/title(2).mp4", FileRepository.buildOutputPath(dir.absolutePath, "title", "mp4", "best"))
    }
    @Test fun buildOutputPath_audioQualityForcesMp3() {
        val dir = createTempDir().absolutePath
        assertEquals("$dir/title.mp3", FileRepository.buildOutputPath(dir, "title", "mp4", "audio"))
    }
    @Test fun buildOutputPath_sanitizesTitle() {
        val dir = createTempDir().absolutePath
        assertEquals("$dir/a_b_c_d.mp4", FileRepository.buildOutputPath(dir, "a/b\\c:d", "mp4", "best"))
    }
}
