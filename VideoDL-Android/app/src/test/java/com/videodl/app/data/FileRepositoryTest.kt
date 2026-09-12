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

/**
 * 中间产物清理的回归测试。
 *
 * 旧实现按"视频标题"做前缀匹配，于是失败一次标题为「猫」的下载，会把用户保存目录里
 * 所有以「猫」开头的文件删掉 —— 包括早就下好的「猫和老鼠.mp4」。这是真实的数据丢失，
 * 所以把判定抽成纯函数在这里钉死。
 */
class PartialCleanupTest {
    @Test fun matchesOwnPartials() {
        val names = listOf("猫.mp4")
        assertTrue("输出文件本身", Naming.isPartialOf("猫.mp4", names))
        assertTrue(Naming.isPartialOf("猫.mp4.part", names))
        assertTrue(Naming.isPartialOf("猫.mp4.compat.mp4", names))
        // yt-dlp 合并前按"主干"命名分片，后缀是点号 + f<id>
        assertTrue("分片视频", Naming.isPartialOf("猫.f137.mp4", names))
        assertTrue("分片音频", Naming.isPartialOf("猫.f140.m4a", names))
        assertTrue(Naming.isPartialOf("猫.part", names))
        assertTrue(Naming.isPartialOf("猫.ytdl", names))
    }

    @Test fun doesNotMatchOtherVideosSharingThePrefix() {
        val names = listOf("猫.mp4")
        assertFalse("同前缀但不同视频，绝不能动", Naming.isPartialOf("猫和老鼠.mp4", names))
        assertFalse("用户自己命名的备份，也不能动", Naming.isPartialOf("猫.mp4 备份.mp4", names))
        assertFalse("主干相同但后缀不像中间产物", Naming.isPartialOf("猫.tmp.mp4", names))
        assertFalse("别的视频", Naming.isPartialOf("狗.f137.mp4", names))
    }

    @Test fun passingABareTitleMatchesNothing() {
        // 万一调用方传进来的是标题（没有扩展名），主干推断会拿到空串 ——
        // 结果是"什么都不匹配"，宁可少删也不多删。这是刻意的保守行为。
        assertFalse(Naming.isPartialOf("猫和老鼠.mp4", listOf("猫")))
        assertFalse(Naming.isPartialOf("猫.mp4", listOf("猫")))
    }

    @Test fun blankPrefixesMatchNothing() {
        assertFalse(Naming.isPartialOf("anything.mp4", listOf("", "  ")))
        assertFalse(Naming.isPartialOf("anything.mp4", emptyList()))
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
    @Test fun buildOutputPath_audioQualityUsesM4a() {
        // 音频产物是 m4a 不是 mp3：打包的 ffmpeg 没有 mp3 编码器，
        // 而 m4a 在源音轨是 AAC 时走 copy，不需要编码器。见 MediaTarget。
        val dir = createTempDir().absolutePath
        assertEquals("$dir/title.m4a", FileRepository.buildOutputPath(dir, "title", "mp4", "audio"))
    }
    @Test fun buildOutputPath_legacyMp3FormatStillAudio() {
        // 老配置里存着 default_format=mp3，不能因为改了容器就当视频处理
        val dir = createTempDir().absolutePath
        assertEquals("$dir/title.m4a", FileRepository.buildOutputPath(dir, "title", "mp3", "best"))
    }
    @Test fun buildOutputPath_sanitizesTitle() {
        val dir = createTempDir().absolutePath
        assertEquals("$dir/a_b_c_d.mp4", FileRepository.buildOutputPath(dir, "a/b\\c:d", "mp4", "best"))
    }
}
