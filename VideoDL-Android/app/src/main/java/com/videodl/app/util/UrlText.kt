package com.videodl.app.util

/**
 * 从一段任意分享文本里抠出 URL。
 *
 * [com.videodl.app.ShareReceiver] 和 [com.videodl.app.MainActivity] 共用 ——
 * 这两处原本各写了一份一模一样的实现，改一处忘另一处就会让"分享直达"和
 * "在 App 里粘贴"识别出不同的链接。
 *
 * 对应的桌面版是 `video_downloader.py::_extract_url_from_text`。
 * 分享文本常见形态是「标题 https://xxx 分享自某App」，所以要先整串试、再用正则找；
 * 中文标点紧跟在链接后面时 `\S+` 会一起吃掉，得手工去掉尾部标点。
 */
internal fun extractUrl(text: String): String {
    val t = text.trim()
    if (t.startsWith("http")) return t.trimTrailingPunctuation()
    Regex("https?://\\S+").find(t)?.let { return it.value.trimTrailingPunctuation() }
    return ""
}

private fun String.trimTrailingPunctuation(): String =
    trimEnd('。', '．', '.', '，', ',', '/', '\\')
