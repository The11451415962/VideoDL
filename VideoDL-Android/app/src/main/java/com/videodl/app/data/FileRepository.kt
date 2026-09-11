package com.videodl.app.data

import android.content.Context
import java.io.File

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

object FileRepository {
    /** 返回 ffmpeg 可执行文件路径；ffmpeg 作为原生库打包在 jniLibs，安装后解压到 nativeLibraryDir（该目录允许执行） */
    fun ffmpegLocation(context: Context): String {
        val ffmpeg = File(context.applicationInfo.nativeLibraryDir, "libffmpeg.so")
        return if (ffmpeg.exists()) ffmpeg.absolutePath else ""
    }

    /** 用标题/名称 + 格式画质构建不冲突的输出路径（与桌面版命名一致） */
    fun buildOutputPath(baseDir: String, baseName: String, format: String, quality: String): String {
        val safeBase = Naming.sanitize(baseName).ifBlank { "video" }
        val ext = if (format == "mp3" || quality == "audio") "mp3" else format
        val existing = File(baseDir).listFiles()?.map { it.name }?.toSet() ?: emptySet()
        return Naming.nextFilePath(baseDir, safeBase, ext, existing)
    }

    fun defaultBaseDir(context: Context): String =
        File(context.getExternalFilesDir(null), "VideoDL").apply { mkdirs() }.absolutePath

    /** 是否已授予「所有文件访问权限」(MANAGE_EXTERNAL_STORAGE，Android 11+ 才有) */
    fun allFilesAccess(): Boolean =
        android.os.Build.VERSION.SDK_INT >= 30 && android.os.Environment.isExternalStorageManager()

    /** 解析保存目录为真实文件路径；SAF content:// 树只有在拥有「所有文件访问权限」时才可解析为可写路径 */
    fun resolveBaseDir(context: Context, config: AppConfig): String {
        val raw = config.saveDirUri
        if (raw.isBlank()) return defaultBaseDir(context)
        if (raw.startsWith("content://")) {
            if (allFilesAccess()) {
                val p = resolveTreeUriToPath(raw)
                if (p != null) return File(p).apply { mkdirs() }.absolutePath
            }
            return defaultBaseDir(context)
        }
        return File(raw).apply { mkdirs() }.absolutePath
    }

    /** 把 SAF 树 URI(content://.../tree/primary:<路径>) 解析成真实文件路径，失败返回 null */
    private fun resolveTreeUriToPath(uriStr: String): String? {
        if (!uriStr.startsWith("content://")) return uriStr
        return try {
            val uri = android.net.Uri.parse(uriStr)
            val docId = android.provider.DocumentsContract.getTreeDocumentId(uri)
            val actual = docId.removePrefix("primary:").removePrefix("primary").removePrefix("/")
            java.io.File(android.os.Environment.getExternalStorageDirectory(), actual).absolutePath
        } catch (_: Exception) {
            null
        }
    }

    /** 把 SAF 树 URI 转成可读的目录名（去掉 URL 编码和存储根前缀），用于界面展示 */
    fun friendlySaveDir(uri: String): String {
        if (uri.isBlank()) return ""
        val treeIdx = uri.lastIndexOf("/tree/")
        if (treeIdx >= 0) {
            val decoded = android.net.Uri.decode(uri.substring(treeIdx + "/tree/".length))
            return decoded.removePrefix("primary:").removePrefix("primary").trimStart('/').ifBlank { decoded }
        }
        return uri
    }
}
