package com.videodl.app.data

import android.content.Context
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore(name = "videodl_config")

interface ConfigRepository {
    val configFlow: Flow<AppConfig>
    suspend fun update(transform: (AppConfig) -> AppConfig)
}

class ConfigRepositoryImpl(private val context: Context) : ConfigRepository {

    private object Keys {
        val SAVE_DIR = stringPreferencesKey("save_dir_uri")
        val PROXY_MODE = stringPreferencesKey("proxy_mode")
        val PROXY_URL = stringPreferencesKey("proxy_url")
        val COOKIE_MODE = stringPreferencesKey("cookie_mode")
        val COOKIE_PATH = stringPreferencesKey("cookie_path_uri")
        val FORMAT = stringPreferencesKey("default_format")
        val QUALITY = stringPreferencesKey("default_quality")
        val AUTO_OPEN = booleanPreferencesKey("auto_open_file")
        val GALLERY = booleanPreferencesKey("export_to_gallery")
    }

    /** 唯一的 Preferences → AppConfig 映射，读、写两侧共用，避免默认值走偏 */
    private fun Preferences.toConfig(): AppConfig = AppConfig(
        saveDirUri = this[Keys.SAVE_DIR] ?: "",
        proxyMode = this[Keys.PROXY_MODE] ?: "auto",
        proxyUrl = this[Keys.PROXY_URL] ?: "http://127.0.0.1:7890",
        cookieMode = this[Keys.COOKIE_MODE] ?: "none",
        cookiePathUri = this[Keys.COOKIE_PATH] ?: "",
        defaultFormat = this[Keys.FORMAT] ?: "mp4",
        defaultQuality = this[Keys.QUALITY] ?: "best",
        autoOpenFile = this[Keys.AUTO_OPEN] != false,
        exportToGallery = this[Keys.GALLERY] != false,
    )

    override val configFlow: Flow<AppConfig> =
        context.dataStore.data.map { it.toConfig() }

    override suspend fun update(transform: (AppConfig) -> AppConfig) {
        context.dataStore.edit { p ->
            val next = transform(p.toConfig())
            p[Keys.SAVE_DIR] = next.saveDirUri
            p[Keys.PROXY_MODE] = next.proxyMode
            p[Keys.PROXY_URL] = next.proxyUrl
            p[Keys.COOKIE_MODE] = next.cookieMode
            p[Keys.COOKIE_PATH] = next.cookiePathUri
            p[Keys.FORMAT] = next.defaultFormat
            p[Keys.QUALITY] = next.defaultQuality
            p[Keys.AUTO_OPEN] = next.autoOpenFile
            p[Keys.GALLERY] = next.exportToGallery
        }
    }
}
