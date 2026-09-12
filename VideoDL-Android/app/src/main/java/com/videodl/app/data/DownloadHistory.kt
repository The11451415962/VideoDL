package com.videodl.app.data

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/** 一条下载记录（下载列表里的一张卡片） */
data class DownloadRecord(
    val id: String,
    val title: String,
    val uri: String,          // 相册 content:// 或本地路径
    val thumb: String,        // 缩略图 URL（可能为空）
    val formatLabel: String,  // 例如 "1080p · mp4"
    val sizeText: String,     // 例如 "31.1 MB"
    val status: String,       // done | error | cancelled
    val timeMs: Long,
    /** 时长文字（卡片左下，对标 YTDLnis 的卡片信息排布） */
    val durationText: String = "",
    /** 上传者（卡片第二行） */
    val uploader: String = "",
    /**
     * 这条记录是音频还是视频。
     *
     * 以前界面靠 `formatLabel.contains("mp3")` 猜，而音频产物已经不叫 mp3 了
     * （见 [MediaTarget]），猜错就会把音频混进"视频"筛选里。所以显式存一位。
     */
    val isAudio: Boolean = false,
)

/**
 * 下载记录持久化。
 *
 * 界面上的"下载"标签页读它；用 JSON 文件而不是 Room —— 记录量小、
 * 结构简单，不值得为它引一整套数据库依赖。
 */
object DownloadHistory {

    private const val FILE_NAME = "downloads.json"
    private const val MAX_RECORDS = 300

    private fun file(ctx: Context) = File(ctx.filesDir, FILE_NAME)

    fun load(ctx: Context): List<DownloadRecord> = try {
        val f = file(ctx)
        if (!f.isFile) emptyList() else decode(f.readText())
    } catch (e: Exception) {
        emptyList()
    }

    /** 列表 → JSON（纯函数，方便不依赖设备做单元测试） */
    internal fun encode(list: List<DownloadRecord>): String {
        val arr = JSONArray()
        list.forEach { r ->
            arr.put(JSONObject().apply {
                put("id", r.id)
                put("title", r.title)
                put("uri", r.uri)
                put("thumb", r.thumb)
                put("format", r.formatLabel)
                put("size", r.sizeText)
                put("status", r.status)
                put("time", r.timeMs)
                put("dur", r.durationText)
                put("up", r.uploader)
                put("audio", r.isAudio)
            })
        }
        return arr.toString()
    }

    /** JSON → 列表；内容损坏时返回空列表而不是抛异常（界面不能因此崩掉） */
    internal fun decode(json: String): List<DownloadRecord> = try {
        val arr = JSONArray(json)
        (0 until arr.length()).mapNotNull { i ->
            val o = arr.optJSONObject(i) ?: return@mapNotNull null
            DownloadRecord(
                id = o.optString("id"),
                title = o.optString("title"),
                uri = o.optString("uri"),
                thumb = o.optString("thumb"),
                formatLabel = o.optString("format"),
                sizeText = o.optString("size"),
                status = o.optString("status", "done"),
                timeMs = o.optLong("time", 0L),
                durationText = o.optString("dur"),
                uploader = o.optString("up"),
                // 老记录没有这个字段：按旧的 formatLabel 猜一次，别把历史音频错分到视频里
                isAudio = if (o.has("audio")) o.optBoolean("audio")
                else looksLikeAudioLabel(o.optString("format")),
            )
        }
    } catch (e: Exception) {
        emptyList()
    }

    /** 兼容旧记录：老版本把音频标成 "… · mp3"。注意不能拿 "mp4" 去匹配，它是视频。 */
    private fun looksLikeAudioLabel(formatLabel: String): Boolean =
        formatLabel.contains("m4a") || formatLabel.contains("mp3")

    fun add(ctx: Context, record: DownloadRecord) {
        val list = load(ctx).filterNot { it.id == record.id }
        save(ctx, (listOf(record) + list).take(MAX_RECORDS))
    }

    fun updateStatus(ctx: Context, id: String, status: String, uri: String = "") {
        val list = load(ctx).map {
            if (it.id == id) it.copy(status = status, uri = uri.ifBlank { it.uri }) else it
        }
        save(ctx, list)
    }

    fun remove(ctx: Context, id: String) {
        save(ctx, load(ctx).filterNot { it.id == id })
    }

    fun clear(ctx: Context) {
        runCatching { file(ctx).delete() }
    }

    private fun save(ctx: Context, list: List<DownloadRecord>) {
        runCatching { file(ctx).writeText(encode(list)) }
    }
}
