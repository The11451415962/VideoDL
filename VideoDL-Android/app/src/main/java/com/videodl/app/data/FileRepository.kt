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
