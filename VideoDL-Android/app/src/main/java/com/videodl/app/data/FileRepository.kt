package com.videodl.app.data

import android.content.ContentValues
import android.content.Context
import android.media.MediaScannerConnection
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
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

    /**
     * yt-dlp 的中间产物后缀：`f137.mp4`（分片）、`part` / `part-FragN`、`ytdl`、`temp`。
     * 只认这些形状，别的都不动。
     */
    private val PARTIAL_SUFFIX = Regex("^(f\\d+\\.|part|ytdl|temp)")

    /**
     * 判断 [fileName] 是不是本次下载留下的中间产物。
     *
     * **必须用完整输出名（含扩展名）做前缀**，不能用视频标题：
     * 标题是用户可见的短词，而落地目录可能是用户自己选的保存目录，
     * 按标题前缀清理会把该目录下所有同名开头的文件一起删掉
     * （失败一次「猫」就带走早就下好的「猫和老鼠.mp4」）。这是真实发生过的数据丢失。
     *
     * 三种命中，都要求**点号边界**，所以「猫.mp4」匹配不到「猫和老鼠.mp4」，
     * 也匹配不到用户自己命名的「猫.mp4 备份.mp4」：
     *   - 名字就是本次输出文件本身（失败时可能留下一个空壳）
     *   - 「猫.mp4.part」「猫.mp4.compat.mp4」：输出名 + 点号 + 后缀
     *   - 「猫.f137.mp4」「猫.f140.m4a」「猫.part」：yt-dlp 合并前按**主干**命名的分片，
     *     后缀形状受限（见 [PARTIAL_SUFFIX]），不是"点号后面什么都删"
     */
    fun isPartialOf(fileName: String, outputFileNames: List<String>): Boolean =
        outputFileNames.any { name ->
            when {
                // 必须传带扩展名的完整文件名。传了个裸标题（没有点号）就当作"不可用"，
                // 宁可什么都不匹配、少删一点，也不要退化成按标题前缀乱删。
                name.isBlank() || '.' !in name -> false
                fileName == name -> true
                fileName.startsWith("$name.") -> true
                else -> {
                    val stem = name.substringBeforeLast('.')
                    if (fileName.startsWith("$stem.")) {
                        PARTIAL_SUFFIX.containsMatchIn(fileName.removePrefix("$stem."))
                    } else {
                        false
                    }
                }
            }
        }
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
        val ext = MediaTarget.ext(format, quality)
        val existing = File(baseDir).listFiles()?.map { it.name }?.toSet() ?: emptySet()
        return Naming.nextFilePath(baseDir, safeBase, ext, existing)
    }

    fun defaultBaseDir(context: Context): String =
        File(context.getExternalFilesDir(null), "VideoDL").apply { mkdirs() }.absolutePath

    /** 相册里的相对目录（用户在相册/剪映里看到的路径） */
    const val GALLERY_SUBDIR = "VideoDL"

    /**
     * 把下好的文件发布到系统媒体库（相册）。
     *
     * 好处有两个：剪映/相册等 App 能直接看到它；而且完全不需要
     * 「所有文件访问」这种敏感权限（Android 10+ 用 MediaStore 写入即可）。
     *
     * 成功返回媒体库的 content:// URI，失败返回 null（调用方保留原文件就是）。
     */
    fun publishToGallery(
        context: Context,
        file: File,
        mime: String = "video/mp4",
        isAudio: Boolean = false,
    ): Uri? {
        if (!file.isFile || file.length() <= 0L) return null
        val resolver = context.contentResolver
        return try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                val collection = if (isAudio) {
                    MediaStore.Audio.Media.EXTERNAL_CONTENT_URI
                } else {
                    MediaStore.Video.Media.EXTERNAL_CONTENT_URI
                }
                val baseDir = if (isAudio) {
                    Environment.DIRECTORY_MUSIC
                } else {
                    Environment.DIRECTORY_MOVIES
                }
                val values = ContentValues().apply {
                    put(MediaStore.MediaColumns.DISPLAY_NAME, file.name)
                    put(MediaStore.MediaColumns.MIME_TYPE, mime)
                    put(MediaStore.MediaColumns.RELATIVE_PATH, "$baseDir/$GALLERY_SUBDIR")
                    put(MediaStore.MediaColumns.IS_PENDING, 1)
                }
                val uri = resolver.insert(collection, values) ?: return null
                val copied = try {
                    resolver.openOutputStream(uri)?.use { out ->
                        file.inputStream().use { input -> input.copyTo(out) }
                    }
                    true
                } catch (e: Exception) {
                    false
                }
                if (!copied) {
                    runCatching { resolver.delete(uri, null, null) }
                    return null
                }
                values.clear()
                values.put(MediaStore.MediaColumns.IS_PENDING, 0)
                resolver.update(uri, values, null, null)
                uri
            } else {
                // Android 9 及以下：直接写公共目录 + 通知媒体扫描（需要 WRITE_EXTERNAL_STORAGE）
                @Suppress("DEPRECATION")
                val publicDir = if (isAudio) {
                    Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_MUSIC)
                } else {
                    Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_MOVIES)
                }
                val dir = File(publicDir, GALLERY_SUBDIR)
                if (!dir.isDirectory && !dir.mkdirs()) return null
                var target = File(dir, file.name)
                var idx = 2
                while (target.exists()) {
                    target = File(dir, "${file.nameWithoutExtension}($idx).${file.extension}")
                    idx++
                }
                file.copyTo(target, overwrite = false)
                MediaScannerConnection.scanFile(context, arrayOf(target.absolutePath), arrayOf(mime), null)
                Uri.fromFile(target)
            }
        } catch (e: Exception) {
            null
        }
    }

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

    /** 用户选的 SAF 目录当前是否真的可写（内部主存储 + 已授权「所有文件访问」）。
     *  为 false 时文件会落到 App 默认目录，界面必须如实告诉用户，不能装作写进去了。 */
    fun canWriteTreeUri(uriStr: String): Boolean =
        uriStr.startsWith("content://") && allFilesAccess() && resolveTreeUriToPath(uriStr) != null

    /** 把 SAF 树 URI(content://.../tree/primary:<路径>) 解析成真实文件路径，失败返回 null */
    private fun resolveTreeUriToPath(uriStr: String): String? {
        if (!uriStr.startsWith("content://")) return uriStr
        return try {
            val uri = android.net.Uri.parse(uriStr)
            val docId = android.provider.DocumentsContract.getTreeDocumentId(uri) ?: return null
            // 只认内部主存储。SD 卡等其它卷的卷名前缀（如 "1234-5678:"）拼到内部存储根上
            // 会得到一个根本不存在的路径 —— 宁可返回 null 回退默认目录，也不要静默写错地方。
            val actual = when {
                docId.startsWith("primary:") -> docId.removePrefix("primary:")
                docId == "primary" -> ""
                else -> return null
            }.trimStart('/')
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
