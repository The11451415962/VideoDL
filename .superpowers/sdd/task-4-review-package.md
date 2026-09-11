# Review Package - Task 4

## Base: 447fa4c  Head: a186872

## Commits
a186872 feat: file naming + sanitize

## Diff stat
 .../java/com/videodl/app/data/FileRepository.kt     | 21 +++++++++++++++++++++
 .../java/com/videodl/app/data/FileRepositoryTest.kt | 18 ++++++++++++++++++
 2 files changed, 39 insertions(+)

## Full diff
diff --git a/VideoDL-Android/app/src/main/java/com/videodl/app/data/FileRepository.kt b/VideoDL-Android/app/src/main/java/com/videodl/app/data/FileRepository.kt
new file mode 100644
index 0000000..cd4dd38
--- /dev/null
+++ b/VideoDL-Android/app/src/main/java/com/videodl/app/data/FileRepository.kt
@@ -0,0 +1,21 @@
+package com.videodl.app.data
+
+object Naming {
+    /**
+     * 在 dir 内生成不冲突的文件路径：base → base(2) → base(3)...
+     * existing: 当前已存在的相对文件名集合（不含路径）。
+     */
+    fun nextFilePath(dir: String, base: String, ext: String,
+                     existing: Set<String> = emptySet(), startAt: Int = 1): String {
+        var idx = startAt
+        while (true) {
+            val name = if (idx == 1) "$base.$ext" else "$base($idx).$ext"
+            if (name !in existing) return "$dir/$name"
+            idx++
+        }
+    }
+
+    /** 仅保留安全文件名字符（与桌面版 re.sub(r'[\\/:*?"<>|]', '_', title) 对应）*/
+    fun sanitize(title: String): String =
+        title.replace(Regex("[\\\\/:*?\"<>|]"), "_").trim()
+}
diff --git a/VideoDL-Android/app/src/test/java/com/videodl/app/data/FileRepositoryTest.kt b/VideoDL-Android/app/src/test/java/com/videodl/app/data/FileRepositoryTest.kt
new file mode 100644
index 0000000..b86902f
--- /dev/null
+++ b/VideoDL-Android/app/src/test/java/com/videodl/app/data/FileRepositoryTest.kt
@@ -0,0 +1,18 @@
+package com.videodl.app.data
+
+import org.junit.Assert.*
+import org.junit.Test
+
+class NamingTest {
+    @Test fun firstAvailable_noSuffix() {
+        assertEquals("/dl/title.mp4", Naming.nextFilePath("/dl", "title", "mp4"))
+    }
+    @Test fun conflict_addsSuffix() {
+        val existing = setOf("title.mp4", "title(2).mp4")
+        assertEquals("/dl/title(3).mp4", Naming.nextFilePath("/dl", "title", "mp4", existing))
+    }
+    @Test fun sanitize_replacesForbiddenChars() {
+        assertEquals("a_b_c_d", Naming.sanitize("a/b\\c:d"))
+        assertEquals("clean title", Naming.sanitize("clean title"))
+    }
+}
