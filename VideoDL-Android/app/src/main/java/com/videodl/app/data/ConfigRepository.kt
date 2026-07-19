package com.videodl.app.data

import android.content.Context
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
    }

    override val configFlow: Flow<AppConfig> = context.dataStore.data.map { p ->
        AppConfig(
            saveDirUri = p[Keys.SAVE_DIR] ?: "",
            proxyMode = p[Keys.PROXY_MODE] ?: "auto",
            proxyUrl = p[Keys.PROXY_URL] ?: "http://127.0.0.1:7897",
            cookieMode = p[Keys.COOKIE_MODE] ?: "none",
            cookiePathUri = p[Keys.COOKIE_PATH] ?: "",
            defaultFormat = p[Keys.FORMAT] ?: "mp4",
            defaultQuality = p[Keys.QUALITY] ?: "best",
            autoOpenFile = p[Keys.AUTO_OPEN] != false,
        )
    }

    override suspend fun update(transform: (AppConfig) -> AppConfig) {
        context.dataStore.edit { p ->
            val cur = AppConfig(
                saveDirUri = p[Keys.SAVE_DIR] ?: "",
                proxyMode = p[Keys.PROXY_MODE] ?: "auto",
                proxyUrl = p[Keys.PROXY_URL] ?: "http://127.0.0.1:7897",
                cookieMode = p[Keys.COOKIE_MODE] ?: "none",
                cookiePathUri = p[Keys.COOKIE_PATH] ?: "",
                defaultFormat = p[Keys.FORMAT] ?: "mp4",
                defaultQuality = p[Keys.QUALITY] ?: "best",
                autoOpenFile = p[Keys.AUTO_OPEN] != false,
            )
            val next = transform(cur)
            p[Keys.SAVE_DIR] = next.saveDirUri
            p[Keys.PROXY_MODE] = next.proxyMode
            p[Keys.PROXY_URL] = next.proxyUrl
            p[Keys.COOKIE_MODE] = next.cookieMode
            p[Keys.COOKIE_PATH] = next.cookiePathUri
            p[Keys.FORMAT] = next.defaultFormat
            p[Keys.QUALITY] = next.defaultQuality
            p[Keys.AUTO_OPEN] = next.autoOpenFile
        }
    }
}
