package com.videodl.app.ui.settings

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
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
import androidx.compose.material3.Button
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.videodl.app.R
import com.videodl.app.data.FileRepository

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(
    vm: SettingsViewModel,
    onBack: () -> Unit,
) {
    val config by vm.config.collectAsState()
    val ctx = LocalContext.current

    // 选 Cookie 文件
    val cookiePicker = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri: Uri? ->
        uri?.let { vm.onCookieFilePicked(it) }
    }

    // 外层 VideoDlApp 已有 Scaffold（含底部导航），这里不再嵌套，避免顶部重复留白
    Column(modifier = Modifier.fillMaxSize()) {
        TopAppBar(
            title = { Text(stringResource(R.string.settings_title)) },
            navigationIcon = {
                IconButton(onClick = onBack) {
                    Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = stringResource(R.string.btn_back))
                }
            },
        )
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 16.dp)
                .verticalScroll(rememberScrollState())
        ) {
            // ---- 保存位置（相册优先）----
            SectionTitle(stringResource(R.string.settings_save_dir))
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
                Text(
                    stringResource(R.string.settings_export_gallery),
                    style = MaterialTheme.typography.bodyLarge,
                    modifier = Modifier.weight(1f)
                )
                Switch(
                    checked = config.exportToGallery,
                    onCheckedChange = vm::onExportToGalleryChanged,
                )
            }
            Spacer(Modifier.height(4.dp))
            Text(
                text = if (config.exportToGallery) stringResource(R.string.settings_dest_gallery)
                       else stringResource(R.string.settings_gallery_off_hint),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            HorizontalDivider(Modifier.padding(vertical = 12.dp))

            // ---- 代理模式 ----
            SectionTitle(stringResource(R.string.settings_proxy_mode))
            DropdownSelector(
                options = listOf("auto" to stringResource(R.string.proxy_auto),
                                  "direct" to stringResource(R.string.proxy_direct),
                                  "proxy" to stringResource(R.string.proxy_force)),
                selected = config.proxyMode,
                onSelect = vm::onProxyModeChanged,
            )

            Spacer(Modifier.height(12.dp))

            // ---- 代理地址 ----
            OutlinedTextField(
                value = config.proxyUrl,
                onValueChange = vm::onProxyUrlChanged,
                label = { Text(stringResource(R.string.settings_proxy_url)) },
                placeholder = { Text(stringResource(R.string.settings_proxy_url_hint)) },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )

            HorizontalDivider(Modifier.padding(vertical = 12.dp))

            // ---- Cookie 模式 ----
            SectionTitle(stringResource(R.string.settings_cookie_mode))
            DropdownSelector(
                options = listOf("none" to stringResource(R.string.cookie_none),
                                  "file" to stringResource(R.string.cookie_file)),
                selected = config.cookieMode,
                onSelect = vm::onCookieModeChanged,
            )

            if (config.cookieMode == "file") {
                Spacer(Modifier.height(12.dp))
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    Text(
                        text = if (config.cookiePathUri.isBlank())
                                   "未选择 Cookie 文件"
                               else
                                   "已选择：" + config.cookiePathUri.substringAfterLast('/'),
                        style = MaterialTheme.typography.bodyMedium,
                        modifier = Modifier.weight(1f),
                    )
                    Spacer(Modifier.width(8.dp))
                    OutlinedButton(onClick = { cookiePicker.launch(arrayOf("*/*")) }) {
                        Text(stringResource(R.string.settings_cookie_browse))
                    }
                }
            }

            HorizontalDivider(Modifier.padding(vertical = 12.dp))

            // ---- 默认格式 ----
            SectionTitle(stringResource(R.string.settings_default_format))
            DropdownSelector(
                options = listOf("mp4" to stringResource(R.string.format_mp4),
                                  "webm" to stringResource(R.string.format_webm),
                                  "mp3" to stringResource(R.string.format_mp3)),
                selected = config.defaultFormat,
                onSelect = vm::onDefaultFormatChanged,
            )

            Spacer(Modifier.height(12.dp))

            // ---- 默认画质 ----
            SectionTitle(stringResource(R.string.settings_default_quality))
            DropdownSelector(
                options = listOf("best" to stringResource(R.string.quality_best),
                                  "1080p" to stringResource(R.string.quality_1080p),
                                  "720p" to stringResource(R.string.quality_720p),
                                  "audio" to stringResource(R.string.quality_audio)),
                selected = config.defaultQuality,
                onSelect = vm::onDefaultQualityChanged,
            )

            HorizontalDivider(Modifier.padding(vertical = 12.dp))

            // ---- 自动打开文件 ----
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.fillMaxWidth()
            ) {
                Text(
                    stringResource(R.string.settings_auto_open),
                    style = MaterialTheme.typography.bodyLarge,
                    modifier = Modifier.weight(1f)
                )
                Switch(checked = config.autoOpenFile, onCheckedChange = vm::onAutoOpenChanged)
            }

            Spacer(Modifier.height(24.dp))
        }
    }
}

@Composable
private fun SectionTitle(text: String) {
    Text(
        text = text,
        style = MaterialTheme.typography.titleSmall,
        color = MaterialTheme.colorScheme.primary,
        modifier = Modifier.padding(bottom = 4.dp),
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun DropdownSelector(
    options: List<Pair<String, String>>,
    selected: String,
    onSelect: (String) -> Unit,
) {
    var expanded by remember { mutableStateOf(false) }
    val label = options.firstOrNull { it.first == selected }?.second ?: selected

    ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }) {
        OutlinedTextField(
            value = label,
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
