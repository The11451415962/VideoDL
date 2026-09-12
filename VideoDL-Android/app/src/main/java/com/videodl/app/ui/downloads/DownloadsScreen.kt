package com.videodl.app.ui.downloads

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalIconButton
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.blur
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.videodl.app.data.DownloadCenter
import com.videodl.app.data.DownloadHistory
import com.videodl.app.data.DownloadRecord
import com.videodl.app.data.DownloadSnapshot
import com.videodl.app.data.DownloadStatus
import com.videodl.app.data.QueuedItem
import com.videodl.app.service.DownloadService
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * 下载列表：进行中的 → 队列 → 历史记录。
 *
 * 卡片版式对标 YTDLnis 的 download_card：大卡片、**缩略图模糊铺满整卡**、中间叠原图、
 * 标题/作者压在左上、左下格式右下日期、右侧一个圆角方形操作按钮。
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DownloadsScreen(onOpenFile: (String) -> Unit) {
    val ctx = LocalContext.current
    val dl by DownloadCenter.state.collectAsState()
    var records by remember { mutableStateOf<List<DownloadRecord>>(emptyList()) }
    var refresh by remember { mutableIntStateOf(0) }
    var filter by remember { mutableStateOf("all") }

    LaunchedEffect(dl.status, dl.finishedUri, refresh) {
        records = withContext(Dispatchers.IO) { DownloadHistory.load(ctx) }
    }

    val shown = remember(records, filter) {
        when (filter) {
            "video" -> records.filter { !it.formatLabel.contains("mp3") && it.status == "done" }
            "audio" -> records.filter { it.formatLabel.contains("mp3") }
            else -> records
        }
    }

    Column(modifier = Modifier.fillMaxSize()) {
        TopAppBar(
            title = { Text("下载") },
            actions = {
                if (records.isNotEmpty()) {
                    IconButton(onClick = {
                        DownloadHistory.clear(ctx)
                        refresh++
                    }) {
                        Icon(Icons.Filled.Delete, contentDescription = "清空记录")
                    }
                }
            },
        )

        // 筛选 chip（对标它的「音频 / 视频 / 命令」那一排）
        Row(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            modifier = Modifier.padding(horizontal = 16.dp),
        ) {
            FilterChip(
                selected = filter == "all",
                onClick = { filter = "all" },
                label = { Text("全部") },
            )
            FilterChip(
                selected = filter == "video",
                onClick = { filter = "video" },
                label = { Text("视频") },
            )
            FilterChip(
                selected = filter == "audio",
                onClick = { filter = "audio" },
                label = { Text("音频") },
            )
        }

        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (dl.status != DownloadStatus.Idle) {
                item { ActiveDownloadCard(dl, onCancel = { DownloadService.cancel(ctx) }) }
            }
            if (dl.queued.isNotEmpty()) {
                item { SectionLabel("队列（${dl.queued.size}）") }
                items(dl.queued, key = { "q-${it.url}" }) { q ->
                    QueuedCard(q, onRemove = { DownloadService.dropQueued(ctx, q.url) })
                }
            }
            if (shown.isEmpty() && dl.status == DownloadStatus.Idle && dl.queued.isEmpty()) {
                item { EmptyHint() }
            }
            items(shown, key = { it.id }) { rec ->
                DownloadRecordCard(
                    rec = rec,
                    onOpen = { onOpenFile(rec.uri) },
                    onDelete = {
                        DownloadHistory.remove(ctx, rec.id)
                        refresh++
                    },
                )
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
private fun EmptyHint() {
    Column(
        modifier = Modifier.fillMaxWidth().padding(top = 60.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text("还没有下载记录", style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(6.dp))
        Text(
            "去「首页」粘贴链接开始下载，完成后会自动存进系统相册",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

/** 卡片底：模糊缩略图铺满 + 中间原图 + 上下压暗，保证白字可读（要在 Box 里调用） */
@Composable
private fun BoxScope.CardBackdrop(thumb: String) {
    if (thumb.isNotBlank()) {
        AsyncImage(
            model = thumb,
            contentDescription = null,
            contentScale = ContentScale.Crop,
            modifier = Modifier.fillMaxSize().blur(24.dp),
        )
        AsyncImage(
            model = thumb,
            contentDescription = null,
            contentScale = ContentScale.Fit,
            modifier = Modifier
                .fillMaxHeight()
                .fillMaxWidth(0.55f)
                .align(Alignment.Center),
        )
        Box(
            Modifier
                .fillMaxSize()
                .background(
                    Brush.verticalGradient(
                        0f to Color(0xD9000000),
                        0.4f to Color(0x40000000),
                        1f to Color(0xD9000000),
                    ),
                ),
        )
    } else {
        Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.surfaceVariant))
    }
}

@Composable
private fun ActiveDownloadCard(dl: DownloadSnapshot, onCancel: () -> Unit) {
    Card(shape = RoundedCornerShape(16.dp), modifier = Modifier.fillMaxWidth().height(190.dp)) {
        Box(Modifier.fillMaxSize()) {
            CardBackdrop(dl.info?.thumbnail.orEmpty())
            Column(Modifier.align(Alignment.TopStart).padding(14.dp)) {
                Text(
                    text = dl.info?.title ?: "准备中…",
                    color = Color.White,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = buildString {
                        append("${dl.percent.toInt()}%")
                        if (dl.speed.isNotBlank()) append("  ·  ↓${dl.speed}")
                        if (dl.eta.isNotBlank()) append("  ·  剩余 ${dl.eta}")
                    },
                    color = Color.White.copy(alpha = 0.85f),
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            IconButton(
                onClick = onCancel,
                modifier = Modifier.align(Alignment.CenterEnd).padding(end = 6.dp),
            ) {
                Icon(Icons.Filled.Close, contentDescription = "取消", tint = Color.White)
            }
            LinearProgressIndicator(
                progress = { (dl.percent / 100f).coerceIn(0f, 1f) },
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .fillMaxWidth()
                    .height(6.dp)
                    .clip(RoundedCornerShape(bottomStart = 16.dp, bottomEnd = 16.dp)),
            )
        }
    }
}

/** 排队中还没开始的一项：没有缩略图，用简单的横条 */
@Composable
private fun QueuedCard(q: QueuedItem, onRemove: () -> Unit) {
    Card(
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant,
        ),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(
                Icons.Filled.Refresh,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.size(20.dp),
            )
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(
                    text = q.url,
                    style = MaterialTheme.typography.bodyMedium,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = "等待中 · ${q.label}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            IconButton(onClick = onRemove) {
                Icon(Icons.Filled.Close, contentDescription = "移出队列")
            }
        }
    }
}

@Composable
private fun DownloadRecordCard(rec: DownloadRecord, onOpen: () -> Unit, onDelete: () -> Unit) {
    Card(shape = RoundedCornerShape(16.dp), modifier = Modifier.fillMaxWidth().height(180.dp)) {
        Box(Modifier.fillMaxSize()) {
            CardBackdrop(rec.thumb)

            Column(Modifier.align(Alignment.TopStart).padding(start = 14.dp, top = 12.dp, end = 60.dp)) {
                Text(
                    text = rec.title,
                    color = Color.White,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                // 第二行优先显示作者（对标它的卡片），没有作者就退而显示体积
                val second = rec.uploader.ifBlank { rec.sizeText }
                if (second.isNotBlank()) {
                    Text(
                        text = second,
                        color = Color.White.copy(alpha = 0.85f),
                        style = MaterialTheme.typography.bodySmall,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }

            // 左下显示时长（它的排布），没有时长就退而显示格式
            Text(
                text = rec.durationText.ifBlank { rec.formatLabel },
                color = Color.White,
                style = MaterialTheme.typography.labelMedium,
                modifier = Modifier.align(Alignment.BottomStart).padding(14.dp),
            )
            Text(
                text = timeLabel(rec.timeMs),
                color = Color.White,
                style = MaterialTheme.typography.labelMedium,
                modifier = Modifier.align(Alignment.BottomEnd).padding(14.dp),
            )

            // 右上角删除（它的实现是多选，这里给个显式入口更好用）
            IconButton(
                onClick = onDelete,
                modifier = Modifier.align(Alignment.TopEnd),
            ) {
                Icon(
                    Icons.Filled.Delete,
                    contentDescription = "删除记录",
                    tint = Color.White.copy(alpha = 0.9f),
                )
            }

            if (rec.uri.isNotBlank() && rec.status == "done") {
                FilledTonalIconButton(
                    onClick = onOpen,
                    shape = RoundedCornerShape(14.dp),
                    modifier = Modifier.align(Alignment.CenterEnd).padding(end = 14.dp),
                ) {
                    Icon(Icons.Filled.PlayArrow, contentDescription = "播放")
                }
            }
        }
    }
}

private fun statusLabel(status: String): String = when (status) {
    "done" -> ""
    "error" -> "失败"
    "cancelled" -> "已取消"
    else -> status
}

private fun timeLabel(ms: Long): String {
    if (ms <= 0) return ""
    return SimpleDateFormat("yyyy年M月dd日 HH:mm", Locale.getDefault()).format(Date(ms))
}
