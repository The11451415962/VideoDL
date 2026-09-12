package com.videodl.app.ui.home

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.videodl.app.engine.FormatOption

/** 把格式列表整理成"视频（按清晰度降序）+ 仅音频"两组 */
internal fun splitFormats(formats: List<FormatOption>): Pair<List<FormatOption>, List<FormatOption>> {
    val useful = formats.filter { it.id.isNotBlank() && (it.vcodec != "none" || it.acodec != "none") }
    val video = useful.filterNot { it.audioOnly }
        .sortedWith(
            compareByDescending<FormatOption> { it.height }
                // 同一清晰度优先 H.264 —— 剪映/相册才认
                .thenByDescending { it.editorFriendly }
                .thenByDescending { it.fps }
                .thenByDescending { it.tbr },
        )
        .distinctBy { "${it.height}-${it.ext}-${it.vcodec.substringBefore('.')}" }
        .take(30)
    val audio = useful.filter { it.audioOnly }
        .sortedWith(compareByDescending<FormatOption> { it.editorFriendly }.thenByDescending { it.abr })
        .take(10)
    return video to audio
}

/**
 * 格式选择底部弹窗 —— 卡片行样式对齐 YTDLnis 的 format_item：
 * 主标签（1080p）+ 备注/format_id，右侧体积与码率。
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FormatSheet(
    formats: List<FormatOption>,
    onDismiss: () -> Unit,
    onPick: (FormatOption) -> Unit,
) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    val (video, audio) = splitFormats(formats)

    ModalBottomSheet(onDismissRequest = onDismiss, sheetState = sheetState) {
        Column(Modifier.padding(horizontal = 16.dp).padding(bottom = 24.dp)) {
            Text("选择格式", style = MaterialTheme.typography.titleLarge)
            Spacer(Modifier.height(2.dp))
            Text(
                "优先列 H.264（剪映、相册可直接导入）；体积为预估大小",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(12.dp))
            if (formats.isEmpty()) {
                Text("没有拿到格式列表，请先点「抓取信息」", style = MaterialTheme.typography.bodyMedium)
            } else {
                LazyColumn(
                    modifier = Modifier.heightIn(max = 460.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    item { SectionLabel("视频") }
                    items(video) { fmt -> FormatRow(fmt) { onPick(fmt) } }
                    if (audio.isNotEmpty()) {
                        item { SectionLabel("仅音频") }
                        items(audio) { fmt -> FormatRow(fmt) { onPick(fmt) } }
                    }
                }
            }
        }
    }
}

@Composable
private fun SectionLabel(text: String) {
    Text(
        text = text,
        style = MaterialTheme.typography.labelLarge,
        color = MaterialTheme.colorScheme.primary,
        modifier = Modifier.padding(top = 4.dp),
    )
}

@Composable
private fun FormatRow(fmt: FormatOption, onClick: () -> Unit) {
    Card(
        onClick = onClick,
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant,
        ),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 14.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                Text(
                    text = buildString {
                        append(fmt.label)
                        if (fmt.fps > 0) append("  ${fmt.fps}fps")
                        if (fmt.note.isNotBlank()) append("  ·  ${fmt.note}")
                    },
                    style = MaterialTheme.typography.titleMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Spacer(Modifier.height(2.dp))
                Text(
                    text = listOf(fmt.codecText, fmt.resolutionText, fmt.ext, fmt.id)
                        .filter { it.isNotBlank() }.joinToString("  ·  "),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                // HEVC/AV1 装进 mp4 也常被剪映拒；这里提前讲清楚，别让用户白下
                if (!fmt.editorFriendly) {
                    Spacer(Modifier.height(2.dp))
                    Text(
                        text = "剪映/相册可能不支持此编码",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.error,
                    )
                }
            }
            Spacer(Modifier.width(12.dp))
            Column(horizontalAlignment = Alignment.End) {
                if (fmt.sizeText.isNotBlank()) {
                    Text(fmt.sizeText, style = MaterialTheme.typography.labelLarge)
                }
                if (fmt.bitrateText.isNotBlank()) {
                    Text(
                        fmt.bitrateText,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }
}
