package com.videodl.app.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 下载记录持久化：JSON 编解码是纯逻辑，不需要设备就能测。
 * （真机上的读写由 DownloadService 调用，见 saveRecord）
 */
class DownloadHistoryCodecTest {

    private fun record(id: String = "1", title: String = "测试视频") = DownloadRecord(
        id = id,
        title = title,
        uri = "content://media/external/video/media/51",
        thumb = "https://example.com/t.jpg",
        formatLabel = "1080p · mp4",
        sizeText = "31.1 MB",
        status = "done",
        timeMs = 1_700_000_000_000L,
        durationText = "4:12",
        uploader = "西维西师傅",
    )

    @Test fun roundTrip_keepsAllFields() {
        val list = listOf(record("1", "第一个"), record("2", "第二个"))
        val decoded = DownloadHistory.decode(DownloadHistory.encode(list))
        assertEquals(2, decoded.size)
        assertEquals(list, decoded)
    }

    @Test fun encode_emptyList() {
        assertEquals(emptyList<DownloadRecord>(), DownloadHistory.decode(DownloadHistory.encode(emptyList())))
    }

    @Test fun decode_brokenJson_returnsEmptyInsteadOfCrashing() {
        // 文件被截断/写坏时不能让"下载"标签页直接崩
        assertEquals(emptyList<DownloadRecord>(), DownloadHistory.decode("这不是 json"))
        assertEquals(emptyList<DownloadRecord>(), DownloadHistory.decode(""))
        assertEquals(emptyList<DownloadRecord>(), DownloadHistory.decode("{\"a\":1}"))
    }

    @Test fun decode_toleratesMissingFields() {
        val list = DownloadHistory.decode("""[{"id":"9","title":"只有标题"}]""")
        assertEquals(1, list.size)
        assertEquals("9", list[0].id)
        assertEquals("只有标题", list[0].title)
        assertEquals("done", list[0].status)   // 缺省状态是 done
        assertEquals("", list[0].uri)
    }

    @Test fun encode_handlesChineseAndQuotes() {
        val tricky = record("3", "标题带\"引号\"和\\反斜杠 与 emoji 🎬")
        val decoded = DownloadHistory.decode(DownloadHistory.encode(listOf(tricky)))
        assertEquals(tricky.title, decoded[0].title)
    }

    @Test fun newestFirst_isServiceResponsibility_butDecodeKeepsOrder() {
        // Service 写记录时用 add()（新记录插到最前）；这里只保证解码不重排
        val list = listOf(record("new"), record("old"))
        val decoded = DownloadHistory.decode(DownloadHistory.encode(list))
        assertEquals("new", decoded[0].id)
        assertTrue(decoded.size == 2)
    }
}
