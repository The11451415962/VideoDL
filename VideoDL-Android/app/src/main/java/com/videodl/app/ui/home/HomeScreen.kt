package com.videodl.app.ui.home

import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Create
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledTonalIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
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
import com.videodl.app.data.DownloadStatus
import com.videodl.app.ui.formatDuration
import com.videodl.app.ui.openFile

/**
 * 首页（新建下载）。版式对标 YTDLnis：
 * 品牌色大字标题 → 胶囊形搜索/输入框 → 结果卡（缩略图铺满 + 文字压在图上 + 右下两个圆形按钮）。
 */
@Composable
fun HomeScreen(
    vm: HomeViewModel,
    onOpenFile: (String) -> Unit,
) {
    val state by vm.state.collectAsState()
    val ctx = LocalContext.current
    var logsExpanded by remember { mutableStateOf(false) }
    var sheetVisible by remember { mutableStateOf(false) }

    LaunchedEffect(state.status, state.errorMessage) {
        if (state.status == DownloadStatus.Error && state.errorMessage.isNotBlank()) {
            Toast.makeText(ctx, "下载失败：${state.errorMessage}", Toast.LENGTH_LONG).show()
        }
    }
    val finished = state.finishedFile
    LaunchedEffect(finished) {
        if (finished != null && state.autoOpenFile) onOpenFile(finished)
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 16.dp)
            .verticalScroll(rememberScrollState()),
    ) {
        Spacer(Modifier.height(10.dp))
        // 品牌色大字标题（对标对方的 YTDLnis 标题）
        Text(
            text = "VideoDL",
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.primary,
        )

        Spacer(Modifier.height(12.dp))

        // 胶囊形输入框：填充式（对标对方的搜索框），左侧粘贴、右侧抓取
        TextField(
            value = state.url,
            onValueChange = vm::onUrlChanged,
            placeholder = { Text("搜索或输入 URL") },
            singleLine = true,
            shape = CircleShape,
            colors = TextFieldDefaults.colors(
                focusedContainerColor = MaterialTheme.colorScheme.surfaceVariant,
                unfocusedContainerColor = MaterialTheme.colorScheme.surfaceVariant,
                focusedIndicatorColor = Color.Transparent,
                unfocusedIndicatorColor = Color.Transparent,
                disabledIndicatorColor = Color.Transparent,
            ),
            leadingIcon = {
                IconButton(onClick = vm::pasteFromClipboard) {
                    Icon(Icons.Filled.Create, contentDescription = "粘贴")
                }
            },
            trailingIcon = {
                if (state.fetching) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(20.dp),
                        strokeWidth = 2.dp,
                    )
                } else {
                    IconButton(
                        onClick = vm::fetch,
                        enabled = state.url.isNotBlank(),
                    ) {
                        Icon(Icons.Filled.Search, contentDescription = "抓取信息")
                    }
                }
            },
            modifier = Modifier.fillMaxWidth(),
        )

        if (state.fetchError.isNotBlank()) {
            Spacer(Modifier.height(8.dp))
            Text(
                "❌ ${state.fetchError}",
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall,
            )
        }

        // 结果卡：缩略图铺满整张卡，文字压在上面，右下两个圆形按钮
        val info = state.info
        if (info != null) {
            Spacer(Modifier.height(14.dp))
            Card(
                shape = RoundedCornerShape(16.dp),
                modifier = Modifier
                    .fillMaxWidth()
                    .height(210.dp),
            ) {
                Box(Modifier.fillMaxSize()) {
                    AsyncImage(
                        model = state.thumbnail,
                        contentDescription = null,
                        contentScale = ContentScale.Crop,
                        modifier = Modifier.fillMaxSize(),
                    )
                    // 压一层渐变，保证白字可读（图上文字方案必须这么做）
                    Box(
                        Modifier
                            .fillMaxSize()
                            .background(
                                Brush.verticalGradient(
                                    0f to Color(0xE6000000),
                                    0.45f to Color(0x66000000),
                                    1f to Color(0xD9000000),
                                ),
                            ),
                    )
                    Column(Modifier.align(Alignment.TopStart).padding(14.dp)) {
                        Text(
                            text = info.title,
                            color = Color.White,
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis,
                        )
                        if (info.uploader.isNotBlank()) {
                            Spacer(Modifier.height(2.dp))
                            Text(
                                text = info.uploader,
                                color = Color.White.copy(alpha = 0.85f),
                                style = MaterialTheme.typography.bodySmall,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                            )
                        }
                    }
                    Text(
                        text = formatDuration(info.duration),
                        color = Color.White,
                        style = MaterialTheme.typography.labelMedium,
                        modifier = Modifier.align(Alignment.BottomStart).padding(14.dp),
                    )
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        modifier = Modifier.align(Alignment.BottomEnd).padding(14.dp),
                    ) {
                        FilledTonalIconButton(
                            onClick = { vm.startAudioDownload() },
                            enabled = !state.busy,
                        ) {
                            Icon(Icons.Filled.PlayArrow, contentDescription = "仅音频")
                        }
                        FilledTonalIconButton(
                            onClick = { vm.startDownload() },
                            enabled = !state.busy,
                        ) {
                            Icon(Icons.Filled.PlayArrow, contentDescription = "下载视频")
                        }
                    }
                }
            }

            Spacer(Modifier.height(10.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                AssistChip(
                    onClick = { sheetVisible = true },
                    enabled = state.formats.isNotEmpty() && !state.busy,
                    label = { Text("选格式（${state.formats.size}）") },
                )
                AssistChip(
                    onClick = { logsExpanded = !logsExpanded },
                    label = { Text(if (logsExpanded) "收起日志" else "下载日志") },
                )
            }
        }

        // 当前下载（已取消也短暂显示一下，让用户知道「停止」生效了）
        if (state.busy || state.status == DownloadStatus.Done ||
            state.status == DownloadStatus.Error || state.status == DownloadStatus.Cancelled
        ) {
            Spacer(Modifier.height(12.dp))
            DownloadStatusCard(
                status = state.status,
                percent = state.percent,
                speed = state.speed,
                eta = state.eta,
                destination = state.destination,
                onCancel = vm::cancel,
                onOpen = { state.finishedFile?.let(onOpenFile) },
                finished = state.finishedFile != null,
            )
        }

        if (logsExpanded) {
            Spacer(Modifier.height(10.dp))
            Card(
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.surfaceVariant,
                ),
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(
                    text = if (state.logs.isEmpty()) "（暂无日志）"
                    else state.logs.takeLast(200).joinToString("\n"),
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(10.dp),
                )
            }
        }
        Spacer(Modifier.height(20.dp))
    }

    if (sheetVisible) {
        FormatSheet(
            formats = state.formats,
            onDismiss = { sheetVisible = false },
            onPick = { fmt ->
                sheetVisible = false
                vm.startDownload(selector = fmt.downloadSelector)
            },
        )
    }
}

/** 当前下载状态卡 */
@Composable
private fun DownloadStatusCard(
    status: DownloadStatus,
    percent: Float,
    speed: String,
    eta: String,
    destination: String,
    onCancel: () -> Unit,
    onOpen: () -> Unit,
    finished: Boolean,
) {
    val statusText = when (status) {
        DownloadStatus.Idle -> "空闲"
        DownloadStatus.Fetching -> "正在获取信息…"
        DownloadStatus.Downloading -> "下载中"
        DownloadStatus.Done -> "下载完成"
        DownloadStatus.Error -> "下载失败"
        DownloadStatus.Cancelled -> "已取消"
    }
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp)) {
            Row(
                horizontalArrangement = Arrangement.SpaceBetween,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(statusText, style = MaterialTheme.typography.titleSmall)
                Text("${percent.toInt()}%", style = MaterialTheme.typography.titleSmall)
            }
            Spacer(Modifier.height(8.dp))
            LinearProgressIndicator(
                progress = { (percent / 100f).coerceIn(0f, 1f) },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(8.dp)
                    .clip(RoundedCornerShape(4.dp)),
            )
            val sub = listOf(
                speed.takeIf { it.isNotBlank() }?.let { "↓$it" },
                eta.takeIf { it.isNotBlank() }?.let { "剩余 $it" },
            ).filterNotNull().joinToString("  ·  ")
            if (sub.isNotBlank()) {
                Spacer(Modifier.height(6.dp))
                Text(
                    sub,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (destination.isNotBlank()) {
                Spacer(Modifier.height(4.dp))
                Text(
                    "保存位置：$destination",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            Spacer(Modifier.height(10.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (status == DownloadStatus.Downloading || status == DownloadStatus.Fetching) {
                    OutlinedButton(onClick = onCancel, modifier = Modifier.weight(1f)) {
                        Icon(Icons.Filled.Close, contentDescription = null)
                        Spacer(Modifier.width(4.dp))
                        Text("停止")
                    }
                } else if (finished) {
                    Button(onClick = onOpen, modifier = Modifier.weight(1f)) {
                        Icon(Icons.Filled.PlayArrow, contentDescription = null)
                        Spacer(Modifier.width(4.dp))
                        Text("播放")
                    }
                    OutlinedButton(onClick = onCancel, enabled = false, modifier = Modifier.weight(1f)) {
                        Text("再下一次")
                    }
                }
            }
        }
    }
}
