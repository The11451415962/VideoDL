package com.videodl.app.data

import org.junit.Assert.*
import org.junit.Test

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
