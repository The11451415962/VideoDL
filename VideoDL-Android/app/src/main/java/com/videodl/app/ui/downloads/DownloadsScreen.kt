package com.videodl.app.ui.downloads

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
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
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import com.videodl.app.data.DownloadCenter
import com.videodl.app.data.DownloadHistory
import com.videodl.app.data.DownloadRecord
import com.videodl.app.data.DownloadSnapshot
import com.videodl.app.service.DownloadService
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * 下载列表：进行中的下载置顶，下面是历史记录。
 * 卡片版式对齐 YTDLnis 的 download_card：缩略图 + 标题 + 一排小标签 + 操作按钮。
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DownloadsScreen(onOpenFile: (String) -> Unit) {
    val ctx = LocalContext.current
    val dl by DownloadCenter.state.collectAsState()
    var records by remember { mutableStateOf<List<DownloadRecord>>(emptyList()) }
    var refresh by remember { mutableIntStateOf(0) }

    LaunchedEffect(dl.status, dl.finishedUri, refresh) {
        records = withContext(Dispatchers.IO) { DownloadHistory.load(ctx) }
    }

    // 不再套自己的 Scaffold：外层 VideoDlApp 的 Scaffold 已经处理了系统栏内边距，
    // 嵌套会导致顶部重复留白
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
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            if (dl.status != com.videodl.app.data.DownloadStatus.Idle) {
                item { ActiveDownloadCard(dl, onCancel = { DownloadService.cancel(ctx) }) }
            }
            if (dl.queued.isNotEmpty()) {
                item { QueueHeader(dl.queued.size) }
                items(dl.queued, key = { "q-${it.url}" }) { q ->
                    QueuedCard(q, onRemove = { DownloadService.dropQueued(ctx, q.url) })
                }
            }
            if (records.isEmpty() && dl.status == com.videodl.app.data.DownloadStatus.Idle) {
                item { EmptyHint() }
            }
            items(records, key = { it.id }) { rec ->
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

@Composable
private fun QueueHeader(count: Int) {
    Text(
        text = "队列（$count）",
        style = MaterialTheme.typography.labelLarge,
        color = MaterialTheme.colorScheme.primary,
        modifier = Modifier.padding(top = 4.dp),
    )
}

/** 排队中还没开始的一项：只能"移除"，因为当前那个正在下 */
@Composable
private fun QueuedCard(q: com.videodl.app.data.QueuedItem, onRemove: () -> Unit) {
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
private fun ActiveDownloadCard(dl: DownloadSnapshot, onCancel: () -> Unit) {
    val title = dl.info?.title ?: "准备中…"
    Card(modifier = Modifier.fillMaxWidth()) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Thumb(dl.info?.thumbnail.orEmpty(), 96, 54)
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(title, style = MaterialTheme.typography.titleSmall, maxLines = 2, overflow = TextOverflow.Ellipsis)
                Spacer(Modifier.height(6.dp))
                LinearProgressIndicator(
                    progress = { (dl.percent / 100f).coerceIn(0f, 1f) },
                    modifier = Modifier.fillMaxWidth().height(6.dp).clip(RoundedCornerShape(3.dp)),
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    text = buildString {
                        append("${dl.percent.toInt()}%")
                        if (dl.speed.isNotBlank()) append("  ·  ↓${dl.speed}")
                        if (dl.eta.isNotBlank()) append("  ·  剩余 ${dl.eta}")
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            IconButton(onClick = onCancel) {
                Icon(Icons.Filled.Close, contentDescription = "取消")
            }
        }
    }
}

@Composable
private fun DownloadRecordCard(rec: DownloadRecord, onOpen: () -> Unit, onDelete: () -> Unit) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Thumb(rec.thumb, 96, 54)
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(rec.title, style = MaterialTheme.typography.titleSmall, maxLines = 2, overflow = TextOverflow.Ellipsis)
                Spacer(Modifier.height(4.dp))
                Text(
                    text = listOfNotNull(
                        rec.formatLabel.takeIf { it.isNotBlank() },
                        rec.sizeText.takeIf { it.isNotBlank() },
                        statusLabel(rec.status),
                        timeLabel(rec.timeMs),
                    ).joinToString("  ·  "),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            if (rec.uri.isNotBlank() && rec.status == "done") {
                IconButton(onClick = onOpen) {
                    Icon(Icons.Filled.PlayArrow, contentDescription = "播放")
                }
            }
            IconButton(onClick = onDelete) {
                Icon(Icons.Filled.Delete, contentDescription = "删除记录")
            }
        }
    }
}

@Composable
private fun Thumb(url: String, w: Int, h: Int) {
    Card(
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant,
        ),
        modifier = Modifier.size(w.dp, h.dp),
    ) {
        if (url.isNotBlank()) {
            AsyncImage(
                model = url,
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxSize(),
            )
        }
    }
}

private fun statusLabel(status: String): String = when (status) {
    "done" -> "已完成"
    "error" -> "失败"
    "cancelled" -> "已取消"
    else -> status
}

private fun timeLabel(ms: Long): String {
    if (ms <= 0) return ""
    return SimpleDateFormat("MM-dd HH:mm", Locale.getDefault()).format(Date(ms))
}
