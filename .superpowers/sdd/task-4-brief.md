# Task 4: 文件命名去重（FileRepository 核心逻辑）

**Files:**
- 创建: `app/src/main/java/com/videodl/app/data/FileRepository.kt`
- 创建: `app/src/test/java/com/videodl/app/data/FileRepositoryTest.kt`

**Interfaces:**
- 产出 `object Naming`（`nextFilePath` 逻辑）；FileRepository.kt 里整体包装 SAF。被 Task 11 HomeViewModel 消费。

- [ ] **Step 1: 写 Naming 工具（翻译桌面版 get_next_filepath）**

```kotlin
package com.videodl.app.data

object Naming {
    /**
     * 在 dir 内生成不冲突的文件路径：base → base(2) → base(3)...
     * existing: 当前已存在的相对文件名集合（不含路径）。
     */
    fun nextFilePath(dir: String, base: String, ext: String,
                     existing: Set<String> = emptySet(), startAt: Int = 1): String {
        var idx = startAt
        while (true) {
            val name = if (idx == 1) "$base.$ext" else "$base($idx).$ext"
            if (name !in existing) return "$dir/$name"
            idx++
        }
    }

    /** 仅保留安全文件名字符（与桌面版 re.sub(r'[\\/:*?"<>|]', '_', title) 对应）*/
    fun sanitize(title: String): String =
        title.replace(Regex("[\\\\/:*?\"<>|]"), "_").trim()
}
```

- [ ] **Step 2: 写测试**

```kotlin
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
```

- [ ] **Step 3: 跑测试**

Run: `./gradlew :app:testDebugUnitTest --tests "com.videodl.app.data.NamingTest"`
预期: PASS

- [ ] **Step 4: 提交**

```bash
git add app/src/main/java/com/videodl/app/data app/src/test
git commit -m "feat: file naming + sanitize"
```
