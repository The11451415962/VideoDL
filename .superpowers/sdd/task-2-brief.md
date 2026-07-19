# Task 2: 配置数据类 AppConfig + ConfigRepository (DataStore)

**Files:**
- 创建: `app/src/main/java/com/videodl/app/data/AppConfig.kt`
- 创建: `app/src/main/java/com/videodl/app/data/ConfigRepository.kt`
- 创建: `app/src/androidTest/java/com/videodl/app/data/ConfigRepositoryTest.kt`

**Interfaces:**
- 产出 `AppConfig` 数据类 + `ConfigRepository`（`data class AppConfig` 被 Task 14 SettingsScreen、Task 9 YtdlpEngineImpl 消费）。

- [ ] **Step 1: 写 AppConfig 数据类**

```kotlin
package com.videodl.app.data

data class AppConfig(
    val saveDirUri: String = "",
    val proxyMode: String = "auto",
    val proxyUrl: String = "http://127.0.0.1:7897",
    val cookieMode: String = "none",
    val cookiePathUri: String = "",
    val defaultFormat: String = "mp4",
    val defaultQuality: String = "best",
    val autoOpenFile: Boolean = true,
)
```

- [ ] **Step 2: 写 ConfigRepository 接口草图（TDD 先写测试）**

```kotlin
package com.videodl.app.data

import android.content.Context
import kotlinx.coroutines.flow.Flow

interface ConfigRepository {
    val configFlow: Flow<AppConfig>
    suspend fun update(transform: (AppConfig) -> AppConfig)
}
```

- [ ] **Step 3: 写 ConfigRepository 实现（DataStore）**

```kotlin
package com.videodl.app.data

import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore(name = "videodl_config")

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
```

- [ ] **Step 4: 写 DataStore 测试**

```kotlin
package com.videodl.app.data

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.With

@RunWith(AndroidJUnit4::class)
class ConfigRepositoryTest {
    @Test
    fun defaultValues_areCorrect() = runBlocking {
        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
        val repo = ConfigRepositoryImpl(ctx)
        val cfg = repo.configFlow.first()
        assertEquals("auto", cfg.proxyMode)
        assertEquals("http://127.0.0.1:7897", cfg.proxyUrl)
        assertEquals("none", cfg.cookieMode)
        assertEquals("mp4", cfg.defaultFormat)
        assertEquals("best", cfg.defaultQuality)
        assertEquals(true, cfg.autoOpenFile)
    }

    @Test
    fun update_persistsChange() = runBlocking {
        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
        val repo = ConfigRepositoryImpl(ctx)
        repo.update { it.copy(proxyMode = "proxy", defaultFormat = "mp3") }
        val cfg = repo.configFlow.first()
        assertEquals("proxy", cfg.proxyMode)
        assertEquals("mp3", cfg.defaultFormat)
    }
}
```

- [ ] **Step 5: 跑测试**

Run: `./gradlew :app:connectedDebugAndroidTest`（需连接真机/模拟器）或 `./gradlew :app:testDebugUnitTest`（把 DataStore 用 robolectric 做单元测亦可）。
预期: PASS

- [ ] **Step 6: 提交**

```bash
git add app/src/main/java/com/videodl/app/data app/src/androidTest
git commit -m "feat: AppConfig + ConfigRepository (DataStore)"
```
