package com.videodl.app.ui.home

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Create
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
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
import android.widget.Toast
import coil.compose.AsyncImage
import com.videodl.app.data.DownloadStatus
import com.videodl.app.ui.formatDuration
import com.videodl.app.ui.openFile

/**
 * 首页：粘贴链接 → 抓取 → 结果卡片（缩略图/标题/时长 + 下载视频 / 仅音频）→ 选格式。
 * 版式对齐 YTDLnis 的 result_card。
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    vm: HomeViewModel,
    onOpenFile: (String) -> Unit,
) {
    val state by vm.state.collectAsState()
    val ctx = LocalContext.current
    var logsExpanded by remember { mutableStateOf(false) }
    var sheetVisible by remember { mutableStateOf(false) }

    // 失败提示
    LaunchedEffect(state.status, state.errorMessage) {
        if (state.status == DownloadStatus.Error && state.errorMessage.isNotBlank()) {
            Toast.makeText(ctx, "下载失败：${state.errorMessage}", Toast.LENGTH_LONG).show()
        }
    }
    // 完成后按设置自动打开
    val finished = state.finishedFile
    LaunchedEffect(finished) {
        if (finished != null && state.autoOpenFile) onOpenFile(finished)
    }

    // 注意：这里不用自己的 Scaffold —— 外层 VideoDlApp 已有 Scaffold（含底部导航），
    // 再套一层会重复叠加系统栏内边距，顶部会多出一大块空白。
    Column(modifier = Modifier.fillMaxSize()) {
        TopAppBar(title = { Text("视频下载器") })
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 16.dp)
                .verticalScroll(rememberScrollState()),
        ) {
            Spacer(Modifier.height(4.dp))

            // ---- 链接输入 ----
            OutlinedTextField(
                value = state.url,
                onValueChange = vm::onUrlChanged,
                placeholder = { Text("粘贴视频链接，例如 https://www.bilibili.com/video/BV...") },
                singleLine = true,
                trailingIcon = {
                    IconButton(onClick = vm::pasteFromClipboard) {
                        Icon(Icons.Filled.Create, contentDescription = "粘贴")
                    }
                },
                modifier = Modifier.fillMaxWidth(),
            )

            Spacer(Modifier.height(8.dp))
            Row(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Button(
                    onClick = vm::fetch,
                    enabled = state.url.isNotBlank() && !state.fetching,
                    modifier = Modifier.weight(1f),
                ) {
                    if (state.fetching) {
                        CircularProgressIndicator(
                            modifier = Modifier.height(18.dp).width(18.dp),
                            strokeWidth = 2.dp,
                        )
                        Spacer(Modifier.width(8.dp))
                        Text("正在抓取…")
                    } else {
                        Text("抓取信息")
                    }
                }
                OutlinedButton(
                    onClick = { sheetVisible = true },
                    enabled = state.formats.isNotEmpty(),
                ) {
                    Text("选格式")
                }
            }

            if (state.fetchError.isNotBlank()) {
                Spacer(Modifier.height(8.dp))
                Text(
                    "❌ ${state.fetchError}",
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall,
                )
            }

            // ---- 结果卡片 ----
            val info = state.info
            if (info != null) {
                Spacer(Modifier.height(12.dp))
                Card(modifier = Modifier.fillMaxWidth()) {
                    Column {
                        AsyncImage(
                            model = state.thumbnail,
                            contentDescription = null,
                            contentScale = ContentScale.Crop,
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(180.dp),
                        )
                        Column(Modifier.padding(14.dp)) {
                            Text(
                                text = info.title,
                                style = MaterialTheme.typography.titleMedium,
                                maxLines = 2,
                                overflow = TextOverflow.Ellipsis,
                            )
                            Spacer(Modifier.height(4.dp))
                            Text(
                                text = listOfNotNull(
                                    info.uploader.takeIf { it.isNotBlank() },
                                    formatDuration(info.duration).takeIf { it != "?" },
                                    "${state.formats.size} 个可用格式",
                                ).joinToString("  ·  "),
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            Spacer(Modifier.height(12.dp))
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                Button(
                                    onClick = { vm.startDownload() },
                                    enabled = !state.busy,
                                    modifier = Modifier.weight(1f),
                                ) {
                                    Icon(Icons.Filled.PlayArrow, contentDescription = null)
                                    Spacer(Modifier.width(4.dp))
                                    Text("下载视频")
                                }
                                OutlinedButton(
                                    onClick = { vm.startAudioDownload() },
                                    enabled = !state.busy,
                                    modifier = Modifier.weight(1f),
                                ) {
                                    Text("仅音频")
                                }
                            }
                            TextButton(
                                onClick = { sheetVisible = true },
                                enabled = state.formats.isNotEmpty() && !state.busy,
                            ) {
                                Text("按格式挑选（${state.formats.size}）")
                            }
                        }
                    }
                }
            }

            // ---- 当前下载 ----
            if (state.busy || state.status == DownloadStatus.Done || state.status == DownloadStatus.Error) {
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

            // ---- 日志（可折叠） ----
            Spacer(Modifier.height(4.dp))
            TextButton(onClick = { logsExpanded = !logsExpanded }) {
                Text(if (logsExpanded) "▼ 收起日志" else "▶ 下载日志（${state.logs.size}）")
            }
            if (logsExpanded) {
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
            Spacer(Modifier.height(16.dp))
        }
    }

    if (sheetVisible) {
        FormatSheet(
            formats = state.formats,
            onDismiss = { sheetVisible = false },
            onPick = { fmt ->
                sheetVisible = false
                // 用 downloadSelector：纯视频流会自动拼音频，否则下出来没声音
                vm.startDownload(selector = fmt.downloadSelector)
            },
        )
    }
}

/** 当前下载状态卡片：进度条 + 速度/剩余 + 停止/播放 */
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
            val sub = listOf(speed.takeIf { it.isNotBlank() }?.let { "↓$it" }, eta.takeIf { it.isNotBlank() }?.let { "剩余 $it" })
                .filterNotNull().joinToString("  ·  ")
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
                        Icon(Icons.Filled.Refresh, contentDescription = null)
                        Spacer(Modifier.width(4.dp))
                        Text("再下一次")
                    }
                }
            }
        }
    }
}
