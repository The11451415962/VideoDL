package com.videodl.app.ui.settings

import android.app.Application
import android.net.Uri
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.videodl.app.data.AppConfig
import com.videodl.app.data.ConfigRepository
import com.videodl.app.data.ConfigRepositoryImpl
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.io.File

class SettingsViewModel(app: Application) : AndroidViewModel(app) {
    private val configRepo: ConfigRepository = ConfigRepositoryImpl(app)

    private val _config = MutableStateFlow(AppConfig())
    val config: StateFlow<AppConfig> = _config.asStateFlow()

    init {
        viewModelScope.launch {
            configRepo.configFlow.collect { _config.value = it }
        }
    }

    private fun update(transform: (AppConfig) -> AppConfig) {
        viewModelScope.launch { configRepo.update(transform) }
    }

    fun onSaveDirChanged(uri: String) = update { it.copy(saveDirUri = uri) }
    fun onProxyModeChanged(mode: String) = update { it.copy(proxyMode = mode) }
    fun onProxyUrlChanged(url: String) = update { it.copy(proxyUrl = url) }
    fun onCookieModeChanged(mode: String) = update { it.copy(cookieMode = mode) }
    fun onCookiePathChanged(path: String) = update { it.copy(cookiePathUri = path) }

    /** 用户从文件选择器选了 cookies.txt：复制到 App 私有目录（yt-dlp 能直接读），并记录路径 */
    fun onCookieFilePicked(uri: Uri) {
        viewModelScope.launch(Dispatchers.IO) {
            try {
                val ctx = getApplication<Application>()
                val dest = File(ctx.filesDir, "cookies.txt")
                ctx.contentResolver.openInputStream(uri)?.use { input ->
                    dest.outputStream().use { output -> input.copyTo(output) }
                }
                configRepo.update { it.copy(cookiePathUri = dest.absolutePath) }
            } catch (_: Exception) {
                // 复制失败则忽略
            }
        }
    }
    fun onDefaultFormatChanged(fmt: String) = update { it.copy(defaultFormat = fmt) }
    fun onDefaultQualityChanged(q: String) = update { it.copy(defaultQuality = q) }
    fun onAutoOpenChanged(b: Boolean) = update { it.copy(autoOpenFile = b) }
}
