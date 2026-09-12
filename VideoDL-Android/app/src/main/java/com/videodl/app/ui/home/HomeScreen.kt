package com.videodl.app.ui.home

import android.content.Intent
import android.widget.Toast
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
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Create
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.videodl.app.R
import com.videodl.app.data.FileRepository

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    vm: HomeViewModel,
    onOpenSettings: () -> Unit,
) {
    val state by vm.state.collectAsState()
    val ctx = LocalContext.current
    var logsExpanded by remember { mutableStateOf(false) }

    // 下载失败时弹窗提示具体原因
    LaunchedEffect(state.status) {
        if (state.status == DownloadStatus.Error && state.errorMessage.isNotBlank()) {
            Toast.makeText(ctx, "下载失败：${state.errorMessage}", Toast.LENGTH_LONG).show()
        }
    }

    // 下载完成后按设置自动打开文件（这个开关以前存了配置但没人读，等于摆设）
    val finishedFile = state.finishedFile
    LaunchedEffect(finishedFile) {
        if (finishedFile != null && state.autoOpenFile) openFile(ctx, finishedFile)
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.app_name)) },
                actions = {
                    IconButton(onClick = onOpenSettings) {
                        Icon(Icons.Filled.Settings, contentDescription = stringResource(R.string.btn_settings))
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp)
                .verticalScroll(rememberScrollState())
        ) {
            // ---- 链接输入 + 粘贴 ----
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.fillMaxWidth()
            ) {
                OutlinedTextField(
                    value = state.url,
                    onValueChange = vm::onUrlChanged,
                    placeholder = { Text(stringResource(R.string.hint_url)) },
                    singleLine = true,
                    modifier = Modifier.weight(1f),
                )
                Spacer(Modifier.width(8.dp))
                IconButton(onClick = vm::pasteFromClipboard) {
                    Icon(Icons.Filled.Create, contentDescription = stringResource(R.string.btn_paste))
                }
            }

            Spacer(Modifier.height(12.dp))

            // ---- 视频信息卡片 ----
            Card(
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.surfaceVariant
                ),
                modifier = Modifier.fillMaxWidth()
            ) {
                val info = state.videoInfo
                if (info != null) {
                    Column(Modifier.padding(12.dp)) {
                        Text(
                            text = info.title,
                            style = MaterialTheme.typography.titleMedium,
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis,
                        )
                        Spacer(Modifier.height(4.dp))
                        Text(
                            text = "${info.uploader}  ·  ${formatDuration(info.duration)}  ·  ${info.resolution}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                } else {
                    Text(
                        text = stringResource(R.string.video_info_placeholder),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(12.dp),
                    )
                }
            }

            Spacer(Modifier.height(12.dp))

            // ---- 格式 / 画质 / 代理 选择 ----
            Row(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                LabeledDropdown(
                    label = stringResource(R.string.label_format),
                    options = listOf("mp4" to stringResource(R.string.format_mp4),
                                      "webm" to stringResource(R.string.format_webm),
                                      "mp3" to stringResource(R.string.format_mp3)),
                    selected = state.format,
                    onSelect = vm::onFormatChanged,
                    modifier = Modifier.weight(1f),
                )
                LabeledDropdown(
                    label = stringResource(R.string.label_quality),
                    options = listOf("best" to stringResource(R.string.quality_best),
                                      "1080p" to stringResource(R.string.quality_1080p),
                                      "720p" to stringResource(R.string.quality_720p),
                                      "audio" to stringResource(R.string.quality_audio)),
                    selected = state.quality,
                    onSelect = vm::onQualityChanged,
                    modifier = Modifier.weight(1f),
                )
                LabeledDropdown(
                    label = stringResource(R.string.label_proxy),
                    options = listOf("auto" to stringResource(R.string.proxy_auto),
                                      "direct" to stringResource(R.string.proxy_direct),
                                      "proxy" to stringResource(R.string.proxy_force)),
                    selected = state.proxyMode,
                    onSelect = vm::onProxyModeChanged,
                    modifier = Modifier.weight(1f),
                )
            }

            Spacer(Modifier.height(16.dp))

            // ---- 进度条 ----
            LinearProgressIndicator(
                progress = { (state.percent / 100f).coerceIn(0f, 1f) },
                modifier = Modifier.fillMaxWidth().height(8.dp),
            )
            Spacer(Modifier.height(4.dp))
            Row(
                horizontalArrangement = Arrangement.SpaceBetween,
                modifier = Modifier.fillMaxWidth()
            ) {
                val statusLabel = when (state.status) {
                    DownloadStatus.Idle -> stringResource(R.string.status_idle)
                    DownloadStatus.Fetching -> stringResource(R.string.status_fetching)
                    DownloadStatus.Downloading -> stringResource(R.string.status_downloading)
                    DownloadStatus.Done -> stringResource(R.string.status_done)
                    DownloadStatus.Error -> stringResource(R.string.status_error)
                }
                Text(
                    text = statusLabel,
                    style = MaterialTheme.typography.bodySmall,
                )
                val speedEta = listOf(state.speed, state.eta).filter { it.isNotBlank() }.joinToString("  ·  ")
                Text(
                    text = if (speedEta.isNotBlank()) "${state.percent.toInt()}%  ·  $speedEta"
                           else "${state.percent.toInt()}%",
                    style = MaterialTheme.typography.bodySmall,
                )
            }

            if (state.status == DownloadStatus.Error && state.errorMessage.isNotBlank()) {
                Spacer(Modifier.height(8.dp))
                Text(
                    text = "❌ ${state.errorMessage}",
                    color = MaterialTheme.colorScheme.error,
                    style = MaterialTheme.typography.bodySmall,
                )
            }

            // 如实显示实际保存目录：选了自定义目录但没授权时会回退到 App 目录，
            // 不写出来用户就会"找不到文件"
            if (state.effectiveSaveDir.isNotBlank()) {
                Spacer(Modifier.height(6.dp))
                Text(
                    text = "保存到：${state.effectiveSaveDir}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }

            Spacer(Modifier.height(12.dp))

            // ---- 按钮组 ----
            Row(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                modifier = Modifier.fillMaxWidth()
            ) {
                Button(
                    onClick = vm::startDownload,
                    enabled = state.status != DownloadStatus.Downloading && state.status != DownloadStatus.Fetching,
                    modifier = Modifier.weight(1f),
                ) {
                    Icon(Icons.Filled.PlayArrow, contentDescription = null)
                    Spacer(Modifier.width(4.dp))
                    Text(stringResource(R.string.btn_download))
                }
                OutlinedButton(
                    onClick = vm::cancel,
                    enabled = state.status == DownloadStatus.Downloading || state.status == DownloadStatus.Fetching,
                    modifier = Modifier.weight(1f),
                ) {
                    Icon(Icons.Filled.Close, contentDescription = null)
                    Spacer(Modifier.width(4.dp))
                    Text(stringResource(R.string.btn_stop))
                }
            }

            val finishedPath = state.finishedFile
            if (finishedPath != null) {
                Spacer(Modifier.height(8.dp))
                Button(
                    onClick = { openFile(ctx, finishedPath) },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(stringResource(R.string.btn_open_file))
                }
            }

            Spacer(Modifier.height(12.dp))

            // ---- 可折叠日志 ----
            TextButton(onClick = { logsExpanded = !logsExpanded }) {
                Text(
                    if (logsExpanded) stringResource(R.string.logs_hide)
                    else stringResource(R.string.logs_show)
                )
            }
            if (logsExpanded) {
                Card(
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.surfaceVariant
                    ),
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text(
                        text = if (state.logs.isEmpty()) "（无日志）"
                               else state.logs.joinToString("\n"),
                        style = MaterialTheme.typography.bodySmall,
                        modifier = Modifier.padding(8.dp),
                    )
                }
            }

            Spacer(Modifier.height(16.dp))
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun LabeledDropdown(
    label: String,
    options: List<Pair<String, String>>,
    selected: String,
    onSelect: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    var expanded by remember { mutableStateOf(false) }
    val displayLabel = options.firstOrNull { it.first == selected }?.second ?: selected

    Column(modifier = modifier) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }) {
            OutlinedTextField(
                value = displayLabel,
                onValueChange = {},
                readOnly = true,
                trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
                modifier = Modifier.menuAnchor().fillMaxWidth(),
            )
            ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
                options.forEach { (value, text) ->
                    DropdownMenuItem(
                        text = { Text(text) },
                        onClick = { onSelect(value); expanded = false },
                    )
                }
            }
        }
    }
}

private fun formatDuration(seconds: Int): String {
    if (seconds <= 0) return "?"
    val m = seconds / 60
    val s = seconds % 60
    return "$m:${s.toString().padStart(2, '0')}"
}

private fun openFile(ctx: android.content.Context, path: String) {
    try {
        val file = java.io.File(path)
        val uri = androidx.core.content.FileProvider.getUriForFile(
            ctx, "${ctx.packageName}.fileprovider", file
        )
        val intent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, "video/*")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        ctx.startActivity(intent)
    } catch (e: Exception) {
        Toast.makeText(ctx, "无法打开文件: ${e.message}", Toast.LENGTH_SHORT).show()
    }
}
