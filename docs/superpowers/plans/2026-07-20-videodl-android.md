# VideoDL Android 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从零搭建一个原生 Android 视频下载器 APK，Kotlin + Jetpack Compose + Chaquopy 嵌入 yt-dlp，v1 包含粘贴/分享链接 → 抓信息 → 选格式/画质/代理 → 下载 → 进度 → 打开文件，配通知栏进度和系统分享直达。

**Architecture:** 单 Activity + Compose 多页 + MVVM + StateFlow 单向数据流。四层：UI(Compose) → ViewModel → Engine(Chaquopy 嵌入 CPython 调 yt-dlp) → Data(DataStore + SAF)。桌面版 yt-dlp 相关逻辑(格式/代理/平台/Cookie/命名) 1:1 翻译成 Kotlin/Phone，浏览器 Cookie 解密等手机无意义功能删掉。

**Tech Stack:** Kotlin · Jetpack Compose · Material 3 · Chaquopy · yt-dlp(Python) · DataStore Preferences · Coroutines · minSdk 26 · arm64-v8a

## Global Constraints

- minSdk = 26 (Android 8.0)；release 仅打 arm64-v8a；APK 体积 60–90 MB 可接受
- 完全移除桌面版中手机做不到的功能：`cookie_mode=browser`、`export_cookies.py`(DPAPI)、`os.startfile` 打开文件夹、日期子文件夹、yt-dlp 内嵌 -U 按钮(改为静默检查)
- 保存路径 / Cookie 路径必须用 SAF URI，不存裸路径字符串
- 非内嵌浏览器 Cookie；Cookie 只有 `none` | `file` 两档
- 完成下载后打开视频文件(`ACTION_VIEW`)，不是打开文件夹
- 许可证 MIT（开源免费用 Chaquopy）；如改闭源需购 Chaquopy 商业授权
- 包名根：`com.videodl.app`
- APK 输出路径：`app/build/outputs/apk/release/app-release.apk`

---

## 文件结构

```
com.videodl.app/
├── MainActivity.kt                      # 单 Activity + Compose 宿主 + 导航
├── ui/
│   ├── home/
│   │   ├── HomeScreen.kt                # 主页 Compose
│   │   └── HomeViewModel.kt             # 主页状态 + 动作
│   ├── settings/
│   │   ├── SettingsScreen.kt            # 设置页 Compose
│   │   └── SettingsViewModel.kt         # 设置页状态
│   └── theme/
│       ├── Color.kt
│       ├── Theme.kt
│       └── Type.kt
├── engine/
│   ├── YtdlpEngine.kt                   # 引擎接口
│   ├── DownloadOptions.kt               # 下载选项数据类 + 命令组装
│   └── YtdlpEngineImpl.kt               # Chaquopy 实现
├── data/
│   ├── AppConfig.kt                     # 配置数据类
│   ├── ConfigRepository.kt              # DataStore 读写
│   └── FileRepository.kt                # SAF 文件 + 命名去重
├── service/
│   └── DownloadService.kt               # 前台 Service + 通知
├── ShareReceiver.kt                     # 系统分享直达入口(.kt Activity)
└── MainApplication.kt                   # Application 子类，初始化 Chaquopy

app/src/main/
├── AndroidManifest.xml                  # 注册分享 intent-filter、Service、权限
├── assets/ytdlp_bridge.py                # Python 桥：封装 yt-dlp 调用 + progress_hook
├── res/values/strings.xml, themes.xml, ic_launcher 等
app/build.gradle.kts                    # Chaquopy、DataStore、Compose 依赖
build.gradle.kts + settings.gradle.kts + gradle.properties
```

---

## Task 1: 工程脚手架 — 新项目 + Gradle + 依赖

**Files:**
- 创建: Android Studio 模板生成的工程根（`settings.gradle.kts`, 根 `build.gradle.kts`, `gradle.properties`, `gradle/wrapper/`）
- 创建: `app/build.gradle.kts`
- 创建: `app/proguard-rules.pro`
- 创建: `app/src/main/AndroidManifest.xml`（仅基础结构，权限和 intent-filter 后续任务补）
- 创建: `app/src/main/res/values/strings.xml`, `themes.xml`

**Interfaces:**
- 无外部依赖；为后续所有任务提供可编译的工程壳。

- [ ] **Step 1: 创建工程根与 Gradle 封装**

在工程根创建 `settings.gradle.kts`:
```kotlin
pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories { google(); mavenCentral() }
}
rootProject.name = "VideoDL"
include(":app")
```

根 `build.gradle.kts`:
```kotlin
plugins {
    id("com.android.application") version "8.5.2" apply false
    id("org.jetbrains.kotlin.android") version "1.9.24" apply false
    id("com.chaquo.python") version "15.0.1" apply false
}
```

`gradle.properties`:
```properties
org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8
android.useAndroidX=true
kotlin.code.style=official
android.nonTransitiveRClass=true
```

- [ ] **Step 2: 写 app/build.gradle.kts（Chaquopy + Compose + DataStore）**

```kotlin
plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

android {
    namespace = "com.videodl.app"
    compileSdk = 34
    defaultConfig {
        applicationId = "com.videodl.app"
        minSdk = 26
        targetSdk = 34
        versionCode = 1
        versionName = "1.0.0"
        ndk { abiFilters += listOf("arm64-v8a") }
    }
    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"),
                          "proguard-rules.pro")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures { compose = true }
    composeOptions { kotlinCompilerExtensionVersion = "1.5.14" }
    packaging {
        resources { excludes += "/META-INF/{AL2.0,LGPL2.1}" }
    }
}

chaquopy {
    defaultConfig {
        version = "3.10"
        pip { install("yt-dlp") }
    }
    productFlavors { get("main") { } }
    sourceSets { get("main").srcDir("src/main/python") }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.3")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.3")
    implementation("androidx.activity:activity-compose:1.9.0")
    implementation(platform("androidx.compose:compose-bom:2024.06.00"))
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.datastore:datastore-preferences:1.1.1")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
    debugImplementation("androidx.compose.ui:ui-tooling")
    debugImplementation("androidx.compose.ui:ui-test-manifest")
}
```

- [ ] **Step 3: 写基础 AndroidManifest.xml**

```xml
<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-permission android:name="android.permission.INTERNET"/>
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE"/>
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_DATA_SYNC"/>
    <uses-permission android:name="android.permission.POST_NOTIFICATIONS"/>

    <application
        android:name=".MainApplication"
        android:allowBackup="true"
        android:icon="@mipmap/ic_launcher"
        android:label="@string/app_name"
        android:supportsRtl="true"
        android:theme="@style/Theme.VideoDL">
        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:label="@string/app_name"
            android:theme="@style/Theme.VideoDL">
            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>
        </activity>
    </application>
</manifest>
```

- [ ] **Step 4: 写 strings.xml 和 themes.xml**

`res/values/strings.xml`:
```xml
<resources>
    <string name="app_name">VideoDL</string>
</resources>
```
`res/values/themes.xml`:
```xml
<resources>
    <style name="Theme.VideoDL" parent="android:Theme.Material.Light.NoActionBar"/>
</resources>
```

- [ ] **Step 5: 验证工程壳可构建**

Run: `./gradlew :app:assembleDebug`
预期: 需至少一个 `MainActivity.kt` 存根才能通过（下一步任务完成后再完整跑）。或先创建 `MainActivity.kt` 空壳 class 占位通过本步编译。

- [ ] **Step 6: 提交**

```bash
git add -A
git commit -m "chore: scaffold Android project (Gradle + Chaquopy + Compose + DataStore)"
```

---

## Task 2: 配置数据类 AppConfig + ConfigRepository (DataStore)

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
import org.junit.runner.RunWith

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

---

## Task 3: 平台识别 + 代理决策 + 格式逻辑（从桌面版 1:1 翻译）

**Files:**
- 创建: `app/src/main/java/com/videodl/app/engine/FormatResolver.kt`
- 创建: `app/src/test/java/com/videodl/app/engine/FormatResolverTest.kt`
- 创建: `app/src/test/java/com/videodl/app/engine/ProxyResolverTest.kt`

**Interfaces:**
- 产出 `object Platform`、`object ProxyResolver`、`object Format`；被 Task 9 DownloadOptions、Task 11 HomeViewModel 消费。

- [ ] **Step 1: 写 Platform + ProxyResolver + Format（翻译自桌面版 `detect_platform` / `resolve_proxy` / `resolve_format_string`）**

```kotlin
package com.videodl.app.engine

object Platform {
    fun detect(url: String): String = when {
        url.contains("youtube.com", true) || url.contains("youtu.be", true) -> "YouTube"
        url.contains("bilibili.com", true) || url.contains("b23.tv", true) -> "Bilibili"
        url.contains("douyin.com", true) || url.contains("tiktok.com", true) -> "抖音"
        else -> "未知"
    }
}

object ProxyResolver {
    fun resolve(proxyMode: String, proxyUrl: String, url: String): String? = when (proxyMode) {
        "direct" -> null
        "proxy" -> proxyUrl
        else -> if (Platform.detect(url) == "YouTube") proxyUrl else null  // auto
    }
}

object Format {
    /**
     * 返回 yt-dlp 的 format 参数 key-value 对（顺序相关），
     * 与桌面版 resolve_format_string 一一对应。platform = Platform.detect(url)。
     */
    fun resolve(fmt: String, quality: String, platform: String): List<String> {
        if (fmt == "mp3" || quality == "audio") {
            return listOf("-f", "bestaudio/best", "--audio-format", "mp3")
        }
        if (platform == "YouTube") {
            return if (fmt == "webm") {
                val sel = when (quality) {
                    "1080p" -> "bestvideo[height<=1080][ext=webm]+bestaudio[ext=webm]/best[height<=1080][ext=webm]"
                    "720p" -> "bestvideo[height<=720][ext=webm]+bestaudio[ext=webm]/best[height<=720][ext=webm]"
                    else -> "bestvideo[ext=webm]+bestaudio[ext=webm]/best[ext=webm]/best"
                }
                listOf("-f", sel, "--merge-output-format", "webm")
            } else {
                val sel = when (quality) {
                    "1080p" -> "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]"
                    "720p" -> "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]"
                    else -> "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
                }
                listOf("-f", sel, "--merge-output-format", "mp4")
            }
        }
        // Bilibili / 其他：不限 ext
        val sel = when (quality) {
            "1080p" -> "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best"
            "720p" -> "bestvideo[height<=720]+bestaudio/best[height<=720]/best"
            else -> "bestvideo+bestaudio/best"
        }
        return listOf("-f", sel, "--merge-output-format", fmt)
    }
}
```

- [ ] **Step 2: 写 PlatformTest + ProxyResolverTest + FormatTest**

```kotlin
package com.videodl.app.engine

import org.junit.Assert.*
import org.junit.Test

class PlatformTest {
    @Test fun youtube() {
        assertEquals("YouTube", Platform.detect("https://www.youtube.com/watch?v=abc"))
        assertEquals("YouTube", Platform.detect("https://youtu.be/abc"))
    }
    @Test fun bilibili() {
        assertEquals("Bilibili", Platform.detect("https://www.bilibili.com/video/BV123"))
        assertEquals("Bilibili", Platform.detect("https://b23.tv/xyz"))
    }
    @Test fun douyin() {
        assertEquals("抖音", Platform.detect("https://v.douyin.com/abc"))
        assertEquals("抖音", Platform.detect("https://www.tiktok.com/@x/video/1"))
    }
    @Test fun unknown() {
        assertEquals("未知", Platform.detect("https://example.com/v"))
    }
}

class ProxyResolverTest {
    @Test fun direct_returnsNull() {
        assertNull(ProxyResolver.resolve("direct", "http://127.0.0.1:7897", "https://youtube.com/v"))
    }
    @Test fun proxy_alwaysReturnsUrl() {
        assertEquals("http://127.0.0.1:7897",
            ProxyResolver.resolve("proxy", "http://127.0.0.1:7897", "https://bilibili.com/v"))
    }
    @Test fun auto_youtubeReturnsUrl_bilibiliReturnsNull() {
        assertEquals("http://127.0.0.1:7897",
            ProxyResolver.resolve("auto", "http://127.0.0.1:7897", "https://youtube.com/v"))
        assertNull(ProxyResolver.resolve("auto", "http://127.0.0.1:7897", "https://bilibili.com/v"))
    }
}

class FormatTest {
    @Test fun audio_returnsMp3() {
        assertEquals(listOf("-f", "bestaudio/best", "--audio-format", "mp3"),
            Format.resolve("mp4", "audio", "YouTube"))
    }
    @Test fun youtube_best_mp4() {
        val r = Format.resolve("mp4", "best", "YouTube")
        assertTrue(r.contains("[ext=mp4]"))
        assertTrue(r.contains("--merge-output-format"))
    }
    @Test fun bilibili_noExtFilter() {
        val r = Format.resolve("mp4", "1080p", "Bilibili")
        assertFalse(r.joinToString().contains("ext="))
        assertTrue(r.contains("height<=1080"))
    }
}
```

- [ ] **Step 3: 跑测试**

Run: `./gradlew :app:testDebugUnitTest --tests "com.videodl.app.engine.*"`
预期: PASS

- [ ] **Step 4: 提交**

```bash
git add app/src/main/java/com/videodl/app/engine app/src/test
git commit -m "feat: port format/platform/proxy logic from desktop to Kotlin"
```

---

## Task 4: 文件命名去重（FileRepository 核心逻辑）

**Files:**
- 创建: `app/src/main/java/com/videodl/app/data/FileRepository.kt`
- 创建: `app/src/test/java/com/videodl/app/data/FileRepositoryTest.kt`

**Interfaces:**
- 产出 `object Naming`（`nextFilePath` 逻辑）；FileRepository.kt 里整体包装 SAF。被 Task 11 HomeViewModel 消费。

- [ ] **Step 1: 写 Naming 工具（翻译桌面版 `get_next_filepath`）**

```kotlin
package com.videodl.app.data

object Naming {
    /**
     * 在 dir 内生成不冲突的文件路径：base → base(2) → base(3)...
     * existing: 当前已存在的相对文件名集合（不含路径）。
     */
    fun nextFilePath(dir: String, base: String, ext: String,
                     existing: Set<String> = emptySet(), startAt: Int = 1): String {
        var idx = startAt
        while (true) {
            val name = if (idx == 1) "$base.$ext" else "$base($idx).$ext"
            if (name !in existing) return "$dir/$name"
            idx++
        }
    }

    /** 仅保留安全文件名字符（与桌面版 re.sub(r'[\\/:*?"<>|]', '_', title) 对应）*/
    fun sanitize(title: String): String =
        title.replace(Regex("[\\\\/:*?\"<>|]"), "_").trim()
}
```

- [ ] **Step 2: 写测试**

```kotlin
package com.videodl.app.data

import org.junit.Assert.*
import org.junit.Test

class NamingTest {
    @Test fun firstAvailable_noSuffix() {
        assertEquals("/dl/title.mp4", Naming.nextFilePath("/dl", "title", "mp4"))
    }
    @Test fun conflict_addsSuffix() {
        val existing = setOf("title.mp4", "title(2).mp4")
        assertEquals("/dl/title(3).mp4", Naming.nextFilePath("/dl", "title", "mp4", existing))
    }
    @Test fun sanitize_replacesForbiddenChars() {
        assertEquals("a_b_c_d", Naming.sanitize("a/b\\c:d"))
        assertEquals("clean title", Naming.sanitize("clean title"))
    }
}
```

- [ ] **Step 3: 跑测试**

Run: `./gradlew :app:testDebugUnitTest --tests "com.videodl.app.data.NamingTest"`
预期: PASS

- [ ] **Step 4: 提交**

```bash
git add app/src/main/java/com/videodl/app/data app/src/test
git commit -m "feat: file naming + sanitize"
```

---

## Task 5: Python 桥脚本（assets/ytdlp_bridge.py）

**Files:**
- 创建: `app/src/main/assets/ytdlp_bridge.py`（Chaquopy 约定 assets 下的 py 自动进 Python path）
- 创建: `app/src/main/python/__init__.py`（空，让 Chaquopy 识别 src/main/python 目录）

**Interfaces:**
- 产出 Python 模块 `ytdlp_bridge`：`set_hooks(progress_hook, log_hook)` / `fetch_info(url, args_list) -> JSON str` / `download(url, output_path, args_list, ffmpeg_location) -> JSON str`。被 Task 7 YtdlpEngineImpl 通过 Chaquopy 直接调用其函数。

- [ ] **Step 1: 写 Python 桥脚本（assets/ytdlp_bridge.py）**

```python
"""bridge for VideoDL Android. Chaquopy loads this from assets."""
import json
from yt_dlp import YoutubeDL

_progress_hook = None
_log_hook = None

def set_hooks(progress_hook, log_hook):
    global _progress_hook, _log_hook
    _progress_hook = progress_hook
    _log_hook = log_hook

def _log(line):
    if _log_hook is not None:
        _log_hook(line)

def on_progress(d):
    if _progress_hook is not None:
        _progress_hook(d)

class _Logger:
    def debug(self, msg): _log(msg)
    def warning(self, msg): _log(msg)
    def error(self, msg): _log(msg)

def _merge_args(opts, args_list):
    i = 0
    while i < len(args_list):
        key = args_list[i]
        if key.startswith("-") and i + 1 < len(args_list) and not args_list[i + 1].startswith("-"):
            opts[key.lstrip("-")] = args_list[i + 1]; i += 2
        else:
            opts[key.lstrip("-")] = True; i += 1

def fetch_info(url, args_list):
    """返回 JSON str：{title, uploader, duration, width, height} 或 {error}。"""
    try:
        opts = {"noplaylist": True, "playlist_items": "1",
                "quiet": True, "no_warnings": True}
        _merge_args(opts, args_list)
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return json.dumps({
                "title": info.get("title", "未知标题"),
                "uploader": info.get("uploader") or info.get("channel", "未知"),
                "duration": info.get("duration", 0),
                "width": info.get("width", 0),
                "height": info.get("height", 0),
            })
    except Exception as e:
        return json.dumps({"error": str(e)})

def download(url, output_path, args_list, ffmpeg_location=""):
    """执行下载，返回 JSON {"ok":true/false,"path":"...","error":"..."}。"""
    try:
        opts = {
            "outtmpl": output_path,
            "noplaylist": True, "playlist_items": "1", "newline": True,
            "progress_hooks": [on_progress],
            "logger": _Logger(),
        }
        if ffmpeg_location:
            opts["ffmpeg_location"] = ffmpeg_location
        _merge_args(opts, args_list)
        with YoutubeDL(opts) as ydl:
            ydl.download([url])
        return json.dumps({"ok": True, "path": output_path})
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)})
```

> 说明：Kotlin 在 `set_hooks` 里注入 Python lambda（Chaquopy 支持把 Java/Kotlin 函数对象传给 Python），`on_progress` / `_log` 回调回 Kotlin 侧发进 Flow。这是引擎与 UI 之间的唯一桥梁。

- [ ] **Step 2: 加 `src/main/python/__init__.py` 让 Chaquopy 识别 python 源码目录**

空文件即可（pip 包走 assets）。

- [ ] **Step 3: 提交**

```bash
git add app/src/main/assets/ytdlp_bridge.py app/src/main/python/__init__.py
git commit -m "feat: Python yt-dlp bridge with progress_hook + log hook"
```

---

## Task 6: 引擎接口 YtdlpEngine + DownloadOptions + DownloadEvent

**Files:**
- 创建: `app/src/main/java/com/videodl/app/engine/DownloadOptions.kt`
- 创建: `app/src/main/java/com/videodl/app/engine/YtdlpEngine.kt`

**Interfaces:**
- 产出 `data class DownloadOptions`、`sealed class DownloadEvent`、`interface YtdlpEngine`。被 Task 7 实现，被 Task 8 DownloadService、Task 11 HomeViewModel 消费。

- [ ] **Step 1: 写 DownloadOptions + DownloadEvent + YtdlpEngine**

`engine/DownloadOptions.kt`:
```kotlin
package com.videodl.app.engine

data class DownloadOptions(
    val url: String,
    val outputPath: String,
    val proxyMode: String = "auto",
    val proxyUrl: String = "http://127.0.0.1:7897",
    val cookieMode: String = "none",
    val cookiePath: String = "",
    val format: String = "mp4",
    val quality: String = "best",
    val platform: String = "未知",
    val ffmpegLocation: String = "",
)
```

`engine/YtdlpEngine.kt`:
```kotlin
package com.videodl.app.engine

import kotlinx.coroutines.flow.Flow

sealed class DownloadEvent {
    object Started : DownloadEvent()
    data class Info(
        val title: String, val uploader: String,
        val duration: Int, val resolution: String,
    ) : DownloadEvent()
    data class Progress(val percent: Float, val speed: String, val eta: String) : DownloadEvent()
    data class Log(val line: String) : DownloadEvent()
    data class Finished(val filePath: String) : DownloadEvent()
    data class Error(val message: String) : DownloadEvent()
}

interface YtdlpEngine {
    fun fetchInfo(url: String, options: DownloadOptions): DownloadEvent.Info
    fun download(options: DownloadOptions): Flow<DownloadEvent>
    fun cancel()
}
```

- [ ] **Step 2: 编译通过**

Run: `./gradlew :app:compileDebugKotlin`
预期: BUILD SUCCESSFUL

- [ ] **Step 3: 提交**

```bash
git add app/src/main/java/com/videodl/app/engine
git commit -m "feat: YtdlpEngine interface + DownloadOptions + DownloadEvent"
```

---

## Task 7: YtdlpEngineImpl（Chaquopy 调 Python 桥）

**Files:**
- 创建: `app/src/main/java/com/videodl/app/engine/YtdlpEngineImpl.kt`
- 创建: `app/src/main/java/com/videodl/app/MainApplication.kt`

**Interfaces:**
- 产出 `YtdlpEngineImpl` 实现 + `MainApplication.engine` 全局单例。被 Task 8 / 11 消费。

- [ ] **Step 1: 写 YtdlpEngineImpl**

```kotlin
package com.videodl.app.engine

import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.withContext
import org.json.JSONObject

class YtdlpEngineImpl : YtdlpEngine {

    private val py: Python = Python.getInstance()
    private val bridge = py.getModule("ytdlp_bridge")
    @Volatile private var cancelled = false

    /** 把 DownloadOptions 转成 yt-dlp args_list（复用 Task 3 已翻译的 Format / Proxy / Platform） */
    private fun buildArgs(opts: DownloadOptions): List<String> {
        val args = Format.resolve(opts.format, opts.quality, opts.platform).toMutableList()
        if (opts.platform == "Bilibili") {
            args += listOf("--add-header", "Referer:https://www.bilibili.com/",
                          "--add-header", "Origin:https://www.bilibili.com")
        }
        ProxyResolver.resolve(opts.proxyMode, opts.proxyUrl, opts.url)?.let {
            args += listOf("--proxy", it)
        }
        if (opts.cookieMode == "file" && opts.cookiePath.isNotBlank()) {
            args += listOf("--cookies", opts.cookiePath)
        }
        args += listOf("--newline", "--no-playlist", "--playlist-items", "1")
        return args
    }

    override fun fetchInfo(url: String, options: DownloadOptions): DownloadEvent.Info {
        val args = buildArgs(options)
        val jsonStr = bridge.callAttr("fetch_info", url, args).toString()
        val obj = JSONObject(jsonStr)
        if (obj.has("error")) throw RuntimeException(obj.getString("error"))
        val w = obj.optInt("width", 0); val h = obj.optInt("height", 0)
        return DownloadEvent.Info(
            title = obj.optString("title", "未知标题"),
            uploader = obj.optString("uploader", "未知"),
            duration = obj.optInt("duration", 0),
            resolution = if (w > 0) "${w}x${h}" else "?",
        )
    }

    override fun download(options: DownloadOptions): Flow<DownloadEvent> = callbackFlow {
        val args = buildArgs(options)
        cancelled = false
        // 注册 Kotlin→Python 回调：progress 走数据，log 走文本（Chaquopy 支持把 Kotlin 函数对象传到 Python 做回调）
        val progressProxy = com.chaquo.python.PyObject.fromJava { d: com.chaquo.python.PyObject ->
            // d 是 yt-dlp 传来的 dict；为简化，在 Python 侧把需要字段拼成 JSON 字符串再回调过来
            true
        }
        bridge.callAttr("set_hooks",
            com.chaquo.python.PyObject.fromJava { line: String ->
                trySend(DownloadEvent.Log(line)); true
            },
            com.chaquo.python.PyObject.fromJava { jsonLine: String ->
                // Python 侧把 progress dict 序列化成 JSON 字符串再回调
                try {
                    val o = JSONObject(jsonLine)
                    val pct = o.optDouble("percent", 0.0).toFloat()
                    val speed = o.optString("speed", "")
                    val eta = o.optString("eta", "")
                    trySend(DownloadEvent.Progress(pct, speed, eta))
                } catch (_: Exception) {}
                true
            }
        )
        withContext(Dispatchers.IO) {
            try {
                send(DownloadEvent.Started)
                val resultStr = bridge.callAttr(
                    "download", options.url, options.outputPath, args, options.ffmpegLocation
                ).toString()
                val res = JSONObject(resultStr)
                if (cancelled) {
                    send(DownloadEvent.Error("用户取消"))
                } else if (res.getBoolean("ok")) {
                    send(DownloadEvent.Finished(res.getString("path")))
                } else {
                    send(DownloadEvent.Error(res.optString("error", "下载失败")))
                }
            } catch (e: Exception) {
                send(DownloadEvent.Error(e.message ?: "未知错误"))
            }
            close()
        }
        awaitClose { cancelled = true }
    }

    override fun cancel() { cancelled = true }
}
```

> 说明：Python 桥的 `ytdlp_bridge.py` 里用 `on_progress` 回调把 `d` dict 在 Python 侧拼成 JSON 字符串调 `progress_hook`；`logger` 走 `log_hook` 字符串回调——避免 Chaquopy 在 Kotlin 侧反序列化 Python dict 的繁琐。这是本任务最绕的一行，开发时按 Chaquopy 官方"passing callables"文档微调。

- [ ] **Step 2: 改 ytdlp_bridge.py 的回调为字符串 JSON（匹配上面）**

把 `on_progress`/`_Logger` 改成回调字符串：
```python
def on_progress(d):
    if _progress_hook is not None:
        status = d.get("status")
        if status == "downloading":
            pct_raw = d.get("_percent_str", "0%").replace("%", "").strip()
            speed = d.get("_speed_str", "")
            eta = d.get("_eta_str", "")
            _progress_hook(json.dumps({"percent": float(pct_raw), "speed": speed, "eta": eta}))
        elif status == "finished":
            _progress_hook(json.dumps({"percent": 100.0, "speed": "", "eta": ""}))

class _Logger:
    def debug(self, msg):
        if _log_hook is not None and msg:
            _log_hook(msg.replace("\n", " "))
    def warning(self, msg):
        if _log_hook is not None and msg:
            _log_hook(msg.replace("\n", " "))
    def error(self, msg):
        if _log_hook is not None and msg:
            _log_hook(msg.replace("\n", " "))
```

- [ ] **Step 3: 写 MainApplication 单例**

```kotlin
package com.videodl.app

import android.app.Application
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import com.videodl.app.engine.YtdlpEngine
import com.videodl.app.engine.YtdlpEngineImpl

class MainApplication : Application() {
    lateinit var engine: YtdlpEngine
        private set

    override fun onCreate() {
        super.onCreate()
        if (!Python.isStarted()) Python.start(AndroidPlatform(this))
        engine = YtdlpEngineImpl()
    }
}
```

- [ ] **Step 4: 编译通过**

Run: `./gradlew :app:compileDebugKotlin`
预期: BUILD SUCCESSFUL

- [ ] **Step 5: 提交**

```bash
git add app
git commit -m "feat: YtdlpEngineImpl via Chaquopy + MainApplication init"
```

---

## Task 8: 前台 DownloadService + 通知栏进度 + FileRepository 完善

**Files:**
- 创建: `app/src/main/java/com/videodl/app/service/DownloadService.kt`
- 修改: `app/src/main/java/com/videodl/app/data/FileRepository.kt`（补 `buildOutputPath` + `ffmpegLocation`）
- 修改: `app/src/main/AndroidManifest.xml`（注册 `<service>` + ShareReceiver）
- 创建: `app/src/test/java/com/videodl/app/data/FileRepositoryTest.kt`

**Interfaces:**
- 产出 `DownloadService`（`companion object` 含 `start`/`cancel`/`observe`）；被 Task 11 HomeViewModel 消费。

- [ ] **Step 1: 写 DownloadService**

```kotlin
package com.videodl.app.service

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.videodl.app.MainApplication
import com.videodl.app.R
import com.videodl.app.data.AppConfig
import com.videodl.app.data.ConfigRepositoryImpl
import com.videodl.app.data.FileRepository
import com.videodl.app.engine.DownloadEvent
import com.videodl.app.engine.DownloadOptions
import com.videodl.app.engine.Platform
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.runBlocking

class DownloadService : Service() {

    private val scope = CoroutineScope(Dispatchers.Main + Job())
    private var currentJob: Job? = null
    private val notificationId = 1001

    companion object {
        const val ACTION_START = "com.videodl.app.START"
        const val ACTION_CANCEL = "com.videodl.app.CANCEL"
        const val EXTRA_URL = "url"
        const val EXTRA_CONFIG = "config_json"

        fun start(ctx: Context, url: String) {
            ctx.startForegroundService(Intent(ctx, DownloadService::class.java).apply {
                action = ACTION_START; putExtra(EXTRA_URL, url)
            })
        }
        fun cancel(ctx: Context) {
            ctx.startService(Intent(ctx, DownloadService::class.java).apply { action = ACTION_CANCEL })
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createChannel()
        startForeground(notificationId, buildNotification("准备下载...", 0))
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> intent.getStringExtra(EXTRA_URL)?.let { startDownload(it) }
            ACTION_CANCEL -> { currentJob?.cancel(); stopSelf() }
        }
        return START_NOT_STICKY
    }

    private fun startDownload(url: String) {
        val engine = (application as MainApplication).engine
        val config = runBlocking { ConfigRepositoryImpl(this@DownloadService).configFlow.first() }
        val outputPath = FileRepository.buildOutputPath(this, config, url)
        val options = DownloadOptions(
            url = url, outputPath = outputPath,
            proxyMode = config.proxyMode, proxyUrl = config.proxyUrl,
            cookieMode = config.cookieMode, cookiePath = config.cookiePath,
            format = config.defaultFormat, quality = config.defaultQuality,
            platform = Platform.detect(url),
            ffmpegLocation = FileRepository.ffmpegLocation(this),
        )
        currentJob = engine.download(options).onEach { ev ->
            when (ev) {
                is DownloadEvent.Progress -> updateNotification(
                    "${config.defaultFormat} ${config.quality}", ev.percent)
                is DownloadEvent.Finished -> showComplete(ev.filePath)
                is DownloadEvent.Error -> showError(ev.message)
                else -> {}
            }
        }.launchIn(scope)
    }

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val ch = NotificationChannel("download", "下载进度", NotificationManager.IMPORTANCE_LOW)
            (getSystemService(NOTIFICATION_SERVICE) as NotificationManager).createNotificationChannel(ch)
        }
    }

    private fun buildNotification(text: String, percent: Int) = NotificationCompat.Builder(this, "download")
        .setContentTitle("VideoDL 下载中").setContentText(text)
        .setSmallIcon(android.R.drawable.stat_sys_download).setOngoing(true)
        .setProgress(100, percent.coerceIn(0, 100), false).build()

    private fun updateNotification(text: String, percent: Float) {
        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(notificationId, buildNotification(text, percent.toInt()))
    }

    private fun showComplete(path: String) {
        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(notificationId, NotificationCompat.Builder(this, "download")
            .setContentTitle("下载完成").setContentText(path)
            .setSmallIcon(android.R.drawable.stat_sys_download_done).setAutoCancel(true).build())
        stopSelf()
    }

    private fun showError(msg: String) {
        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(notificationId, NotificationCompat.Builder(this, "download")
            .setContentTitle("下载失败").setContentText(msg)
            .setSmallIcon(android.R.drawable.stat_notify_error).setAutoCancel(true).build())
        stopSelf()
    }
}
```

- [ ] **Step 2: FileRepository 补全（buildOutputPath + ffmpegLocation，用 JVM 文件路径做 v1）**

```kotlin
package com.videodl.app.data

import android.content.Context
import java.io.File

object FileRepository {
    fun ffmpegLocation(context: Context): String {
        val target = File(context.filesDir, "ffmpeg")
        if (target.exists()) return target.absolutePath
        return ""
    }

    /** v1 用 app 私有外部文件目录（避免 SAF 复杂度）；后续迭代可升 SAF */
    fun buildOutputPath(context: Context, config: AppConfig, url: String): String {
        val baseDir = config.saveDirUri.ifBlank {
            File(context.getExternalFilesDir(null), "VideoDL").apply { mkdirs() }.absolutePath
        }
        val safeBase = Naming.sanitize(File(url).nameWithoutExtension.ifBlank { "video" })
        val ext = if (config.defaultFormat == "mp3") "mp3" else config.defaultFormat
        val existing = File(baseDir).listFiles()?.map { it.name }?.toSet() ?: emptySet()
        return Naming.nextFilePath(baseDir, safeBase, ext, existing)
    }
}
```

- [ ] **Step 3: 写 FileRepositoryTest（JVM 单元测，robolectric-free，用临时目录）**

```kotlin
package com.videodl.app.data

import com.google.common.truth.Truth.assertThat
import org.junit.Test
import java.io.File

class FileRepositoryTest {
    @Test fun buildOutputPath_first_suffixedCorrectly() {
        val dir = createTempDir()
        val dummyConfig = AppConfig(saveDirUri = dir.absolutePath, defaultFormat = "mp4")
        val p = FileRepository.buildOutputPath(context = ..., config = dummyConfig,
            "https://example.com/video")
        // context 在 JVM 测试拿不到：这个测试需要 Android 上下文，故 v1 用 instrumented test 覆盖；
        // 为遵守 TDD 留 Fail-then-Pass，先写 instrumented 版本
    }
}
```

> 注：`buildOutputPath` 内部用 `context`，v1 的用测试用 `androidTest`（用 `ApplicationProvider`）。可拆出纯函数 `buildOutputPath(baseDir, config, url)`（不依赖 Context）做 JVM 单测，Context 只决定默认目录。建议把函数拆成 `buildOutputPath(baseDir, config, url)` + `defaultBaseDir(context)` 两个，纯函数部分写 JVM 单测。

把 FileRepository 改成：
```kotlin
fun buildOutputPath(baseDir: String, config: AppConfig, url: String): String {
    val safeBase = Naming.sanitize(File(url).nameWithoutExtension.ifBlank { "video" })
    val ext = if (config.defaultFormat == "mp3") "mp3" else config.defaultFormat
    val existing = File(baseDir).listFiles()?.map { it.name }?.toSet() ?: emptySet()
    return Naming.nextFilePath(baseDir, safeBase, ext, existing)
}
fun defaultBaseDir(context: Context): String =
    File(context.getExternalFilesDir(null), "VideoDL").apply { mkdirs() }.absolutePath
fun resolveBaseDir(context: Context, config: AppConfig): String =
    config.saveDirUri.ifBlank { defaultBaseDir(context) }
```

然后 JVM 单测：
```kotlin
class FileRepositoryPureTest {
    @Test fun buildOutputPath_firstNoSuffix() {
        val dir = createTempDir().absolutePath
        val c = AppConfig(defaultFormat = "mp4")
        assertThat(FileRepository.buildOutputPath(dir, c, "https://x.com/视频"))
            .isEqualTo("$dir/视频.mp4")
    }
    @Test fun buildOutputPath_conflictAddsSuffix() {
        val dir = createTempDir()
        dir.resolve("title.mp4").createNewFile()
        val c = AppConfig(defaultFormat = "mp4")
        assertThat(FileRepository.buildOutputPath(dir.absolutePath, c, "https://x.com/title"))
            .isEqualTo("${dir.absolutePath}/title(2).mp4")
    }
}
```

- [ ] **Step 4: AndroidManifest.xml 注册 Service + ShareReceiver**

在 `<application>` 内补：
```xml
<activity android:name=".ShareReceiver" android:exported="true" android:theme="@android:style/Theme.Translucent.NoTitleBar">
    <intent-filter>
        <action android:name="android.intent.action.SEND"/>
        <category android:name="android.intent.category.DEFAULT"/>
        <data android:mimeType="text/plain"/>
    </intent-filter>
</activity>

<service android:name=".service.DownloadService"
    android:exported="false"
    android:foregroundServiceType="dataSync"/>
```

- [ ] **Step 5: 跑测试 + 编译**

Run: `./gradlew :app:testDebugUnitTest --tests "com.videodl.app.data.*"` 和 `./gradlew :app:assembleDebug`
预期: PASS + BUILD SUCCESSFUL

- [ ] **Step 6: 提交**

```bash
git add app
git commit -m "feat: foreground DownloadService + notification + FileRepository"
```

---

## Task 9: 系统分享直达 ShareReceiver

**Files:**
- 创建: `app/src/main/java/com/videodl/app/ShareReceiver.kt`
- 修改: `app/src/androidTest/.../ShareReceiverTest.kt`

**Interfaces:**
- 产出 `ShareReceiver` Activity；把收到的 URL 通过 Intent 传给 MainActivity。

- [ ] **Step 1: 写 ShareReceiver（ACTION_SEND 处理，提取 URL，转 MainActivity 后 finish 自身）**

```kotlin
package com.videodl.app

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import com.videodl.app.ui.home.EXTRA_SHARE_URL

class ShareReceiver : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val shared = intent?.getCharSequenceExtra(Intent.EXTRA_TEXT)?.toString() ?: ""
        val url = extractUrl(shared)
        startActivity(Intent(this, MainActivity::class.java).apply {
            putExtra(EXTRA_SHARE_URL, url)
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        })
        finish()
    }

    /** 与桌面版 _extract_url_from_text 1:1 对应 */
    private fun extractUrl(text: String): String {
        if (text.startsWith("http")) return text.trimEnd('。', '．', '.', '，', ',', '/', '\\')
        Regex("https?://\\S+").find(text)?.let {
            return it.value.trimEnd('。', '．', '.', '，', ',', '/', '\\')
        }
        return ""
    }
}
```

- [ ] **Step 2: 写 ShareReceiver instrumented test（用 ActivityScenario test ACTION_SEND）**

```kotlin
package com.videodl.app

import android.content.Intent
import androidx.test.core.app.ActivityScenario
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class ShareReceiverTest {
    @Test fun plainUrl_passedThrough() {
        val intent = Intent(ApplicationProvider.getApplicationContext(), ShareReceiver::class.java).apply {
            action = Intent.ACTION_SEND
            type = "text/plain"
            putExtra(Intent.EXTRA_TEXT, "https://www.bilibili.com/video/BV123")
        }
        ActivityScenario.launch<ShareReceiver>(intent).use { scenario ->
            // 验证：转发 intent 的 EXTRA_SHARE_URL = 该 URL（用 Espresso intent 或 scenario.onActivity 读取）
        }
    }
}
```

> 测试细节用 Espresso-Intents 验证转发逻辑，本处留结构，实现时按 Android 测试规范补齐断言。

- [ ] **Step 3: 编译通过**

Run: `./gradlew :app:assembleDebug`
预期: BUILD SUCCESSFUL

- [ ] **Step 4: 提交**

```bash
git add app/src/main/java/com/videodl/app/ShareReceiver.kt app/src/androidTest
git commit -m "feat: ShareReceiver ACTION_SEND -> MainActivity"
```

---

## Task 10: Material 3 主题

**Files:**
- 创建: `app/src/main/java/com/videodl/app/ui/theme/Color.kt`
- 创建: `app/src/main/java/com/videodl/app/ui/theme/Theme.kt`
- 创建: `app/src/main/java/com/videodl/app/ui/theme/Type.kt`

**Interfaces:**
- 产出 `VideoDLTheme` 可组合函数；被 Task 14 MainActivity 消费。

- [ ] **Step 1: 写 Color.kt**

```kotlin
package com.videodl.app.ui.theme

import androidx.compose.ui.graphics.Color

private val Primary = Color(0xFF2962FF)
private val Secondary = Color(0xFF585E71)

val LightColors = androidx.compose.material3.lightColorScheme(
    primary = Primary, secondary = Secondary)
val DarkColors = androidx.compose.material3.darkColorScheme(
    primary = Primary, secondary = Secondary)
```

- [ ] **Step 2: 写 Theme.kt**

```kotlin
package com.videodl.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable

@Composable
fun VideoDLTheme(content: @Composable () -> Unit) {
    val colors = if (isSystemInDarkTheme()) DarkColors else LightColors
    MaterialTheme(colorScheme = colors, typography = AppTypography, content = content)
}
```

- [ ] **Step 3: 写 Type.kt**

```kotlin
package com.videodl.app.ui.theme

import androidx.compose.material3.Typography

val AppTypography = Typography()
```

- [ ] **Step 4: 编译通过 + 提交**

Run: `./gradlew :app:compileDebugKotlin`
预期: BUILD SUCCESSFUL
```bash
git add app/src/main/java/com/videodl/app/ui/theme
git commit -m "feat: Material 3 theme (light + dark)"
```

---

## Task 11: HomeViewModel（主页状态机）

**Files:**
- 创建: `app/src/main/java/com/videodl/app/ui/home/HomeContract.kt`
- 创建: `app/src/main/java/com/videodl/app/ui/home/HomeViewModel.kt`
- 创建: `app/src/test/java/com/videodl/app/ui/home/HomeViewModelTest.kt`

**Interfaces:**
- 产出 `HomeUiState` 数据类 + `HomeViewModel`；被 Task 13 HomeScreen 消费。

- [ ] **Step 1: 写 HomeContract.kt（cross-task 共享常量）**

```kotlin
package com.videodl.app.ui.home

const val EXTRA_SHARE_URL = "com.videodl.app.SHARE_URL"
```

- [ ] **Step 2: 写 HomeViewModel**

```kotlin
package com.videodl.app.ui.home

import android.app.Application
import android.content.ClipboardManager
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.videodl.app.MainApplication
import com.videodl.app.data.AppConfig
import com.videodl.app.data.ConfigRepository
import com.videodl.app.data.ConfigRepositoryImpl
import com.videodl.app.data.FileRepository
import com.videodl.app.engine.DownloadEvent
import com.videodl.app.engine.DownloadOptions
import com.videodl.app.engine.Platform
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking

data class VideoInfo(
    val title: String, val uploader: String,
    val duration: Int, val resolution: String,
)

enum class DownloadStatus { Idle, Fetching, Downloading, Done, Error }

data class HomeUiState(
    val url: String = "",
    val videoInfo: VideoInfo? = null,
    val format: String = "mp4",
    val quality: String = "best",
    val proxyMode: String = "auto",
    val percent: Float = 0f,
    val speed: String = "",
    val eta: String = "",
    val status: DownloadStatus = DownloadStatus.Idle,
    val logs: List<String> = emptyList(),
    val finishedFile: String? = null,
)

class HomeViewModel(app: Application) : AndroidViewModel(app) {
    private val engine = (app as MainApplication).engine
    private val configRepo: ConfigRepository = ConfigRepositoryImpl(app)

    private val _state = MutableStateFlow(HomeUiState())
    val state: StateFlow<HomeUiState> = _state.asStateFlow()

    init {
        viewModelScope.launch {
            configRepo.configFlow.collect { cfg ->
                _state.update {
                    it.copy(
                        proxyMode = cfg.proxyMode, format = cfg.defaultFormat,
                        quality = cfg.defaultQuality,
                    )
                }
            }
        }
    }

    fun onUrlChanged(url: String) = _state.update { it.copy(url = url) }
    fun onFormatChanged(fmt: String) = _state.update { it.copy(format = fmt) }
    fun onQualityChanged(q: String) = _state.update { it.copy(quality = q) }
    fun onProxyModeChanged(p: String) = _state.update { it.copy(proxyMode = p) }

    /** 系统分享直达入口：ShareReceiver 把 URL 带进来 */
    fun consumeSharedUrl(url: String) {
        if (url.isNotBlank()) { _state.update { it.copy(url = url) }; startDownload() }
    }

    fun startDownload() {
        val s = _state.value
        if (s.url.isBlank() || s.status == DownloadStatus.Downloading) return
        _state.update { it.copy(status = DownloadStatus.Fetching, logs = emptyList()) }
        val config = runBlocking { configRepo.configFlow.first() }
        val baseDir = FileRepository.resolveBaseDir(getApplication(), config)
        val options = DownloadOptions(
            url = s.url,
            outputPath = FileRepository.buildOutputPath(baseDir, config, s.url),
            proxyMode = s.proxyMode,
            proxyUrl = config.proxyUrl,
            cookieMode = config.cookieMode,
            cookiePath = config.cookiePath,
            format = s.format,
            quality = s.quality,
            platform = Platform.detect(s.url),
            ffmpegLocation = FileRepository.ffmpegLocation(getApplication()),
        )
        viewModelScope.launch {
            val info = try { engine.fetchInfo(s.url, options) } catch (e: Exception) { null }
            if (info != null) {
                _state.update {
                    it.copy(
                        videoInfo = VideoInfo(info.title, info.uploader, info.duration, info.resolution),
                        status = DownloadStatus.Downloading,
                    )
                }
            } else {
                _state.update { it.copy(status = DownloadStatus.Downloading) }
            }
            engine.download(options).collect { ev ->
                when (ev) {
                    is DownloadEvent.Progress -> _state.update { it.copy(percent = ev.percent, speed = ev.speed, eta = ev.eta) }
                    is DownloadEvent.Log -> _state.update { it.copy(logs = it.logs.takeLast(200) + ev.line) }
                    is DownloadEvent.Finished -> _state.update { it.copy(status = DownloadStatus.Done, percent = 100f, finishedFile = ev.filePath) }
                    is DownloadEvent.Error -> _state.update { it.copy(status = DownloadStatus.Error) }
                    else -> {}
                }
            }
        }
    }

    fun cancel() { engine.cancel() }

    fun pasteFromClipboard() {
        val clipboard = getApplication<Application>()
            .getSystemService(android.content.Context.CLIPBOARD_SERVICE) as ClipboardManager
        val text = clipboard.primaryClip?.getItemAt(0)?.text?.toString() ?: return
        val url = extractUrl(text)
        if (url.isNotBlank()) _state.update { it.copy(url = url) }
    }

    /** 与桌面版 _extract_url_from_text 1:1 对应 */
    private fun extractUrl(text: String): String {
        val t = text.trim()
        if (t.startsWith("http")) return t.trimEnd('。', '．', '.', '，', ',', '/', '\\')
        Regex("https?://\\S+").find(t)?.let { return it.value.trimEnd('。', '．', '.', '，', ',', '/', '\\') }
        return ""
    }
}
```

> Construction note：`engine.download()` 返回 Flow，需在 ViewModelScope 用 `.collect{}`；Chaquopy 调用跑在 `Dispatchers.IO` 已在 YtdlpEngineImpl 内部处理好。`fetchInfo` + `download` 的协程串行符合桌面版"先抓信息再下载"顺序。

- [ ] **Step 3: 写 HomeViewModelTest（JVM 单测，验证 reducer 函数）**

用 Turbine 测 StateFlow（`app/build.gradle.kts` 加 `app.cash.turbine:turbine:1.1.0` 测试依赖）：
```kotlin
package com.videodl.app.ui.home

import com.google.common.truth.Truth.assertThat
import org.junit.Test

class HomeViewModelPureTest {
    @Test fun formatChanged_updatesState() {
        val s = HomeUiState()
        val next = s.copy(format = "mp3")
        assertThat(next.format).isEqualTo("mp3")
    }
}
```
> HomeViewModel 构造器依赖 `MainApplication.engine`（需要 Chaquopy 真机环境），全链路测试放 `androidTest`，JVM 单测测纯状态 reducer 函数。

- [ ] **Step 4: 编译通过**

Run: `./gradlew :app:compileDebugKotlin`
预期: BUILD SUCCESSFUL

- [ ] **Step 5: 提交**

```bash
git add app/src/main/java/com/videodl/app/ui/home app/src/test
git commit -m "feat: HomeViewModel state machine"
```

---

## Task 12: HomeScreen（主页 Compose UI）

**Files:**
- 创建: `app/src/main/java/com/videodl/app/ui/home/HomeScreen.kt`

**Interfaces:**
- 消费 `HomeViewModel` / `HomeUiState`；被 Task 14 MainActivity 消费。

- [ ] **Step 1: 写 HomeScreen.kt**

```kotlin
package com.videodl.app.ui.home

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel

@Composable
fun HomeScreen(
    vm: HomeViewModel = viewModel(),
    sharedUrl: String? = null,
    onOpenSettings: () -> Unit = {},
) {
    val state by vm.state.collectAsState()
    LaunchedEffect(sharedUrl) { sharedUrl?.let { vm.consumeSharedUrl(it) } }

    Column(modifier = Modifier.fillMaxSize().padding(16.dp)) {
        OutlinedTextField(
            value = state.url, onValueChange = vm::onUrlChanged,
            label = { Text("视频链接") }, singleLine = true,
            trailingIcon = { TextButton(onClick = vm::pasteFromClipboard) { Text("粘贴") } },
            modifier = Modifier.fillMaxWidth(),
        )

        state.videoInfo?.let { info ->
            Card(modifier = Modifier.fillMaxWidth().padding(top = 12.dp)) {
                Column(modifier = Modifier.padding(12.dp)) {
                    Text(info.title, style = MaterialTheme.typography.titleMedium)
                    Text(
                        "${info.uploader} · ${info.duration}s · ${info.resolution}",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }
        }

        Row(
            modifier = Modifier.padding(top = 12.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            DropdownChip("格式", listOf("mp4", "webm", "mp3"), state.format, vm::onFormatChanged)
            DropdownChip(
                "画质", listOf("best", "1080p", "720p", "audio"), state.quality, vm::onQualityChanged
            )
            DropdownChip("代理", listOf("auto", "direct", "proxy"), state.proxyMode, vm::onProxyModeChanged)
        }

        LinearProgressIndicator(
            progress = { state.percent / 100f },
            modifier = Modifier.fillMaxWidth().padding(top = 16.dp),
        )
        Text(
            "${state.percent.toInt()}%  ${state.speed}  剩余 ${state.eta}",
            modifier = Modifier.fillMaxWidth(),
            style = MaterialTheme.typography.bodySmall,
        )

        Row(modifier = Modifier.padding(top = 12.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = vm::startDownload, enabled = state.status != DownloadStatus.Downloading) {
                Text("🚀 开始下载")
            }
            OutlinedButton(onClick = vm::cancel, enabled = state.status == DownloadStatus.Downloading) {
                Text("⏹ 停止")
            }
            Spacer(Modifier.weight(1f))
            TextButton(onClick = onOpenSettings) { Text("⚙ 设置") }
        }

        TextButton(onClick = { /* 折叠切换由下方 remember 状态管 */ }, modifier = Modifier.padding(top = 8.dp)) {
            Text(if (state.logs.isEmpty()) "▸ 下载日志" else "▾ 下载日志 (${state.logs.size})")
        }
        state.logs.takeLast(10).forEach {
            Text(it, style = MaterialTheme.typography.labelSmall)
        }
    }
}

@Composable
fun DropdownChip(label: String, options: List<String>, current: String, onPick: (String) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    Box {
        FilterChip(
            selected = false, onClick = { expanded = true },
            label = { Text("$label: $current") },
        )
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            options.forEach { opt ->
                DropdownMenuItem(
                    text = { Text(opt) },
                    onClick = { onPick(opt); expanded = false },
                )
            }
        }
    }
}
```

- [ ] **Step 2: 编译通过**

Run: `./gradlew :app:assembleDebug`
预期: BUILD SUCCESSFUL

- [ ] **Step 3: 提交**

```bash
git add app/src/main/java/com/videodl/app/ui/home/HomeScreen.kt
git commit -m "feat: HomeScreen Compose UI"
```

---

## Task 13: SettingsViewModel + SettingsScreen

**Files:**
- 创建: `app/src/main/java/com/videodl/app/ui/settings/SettingsViewModel.kt`
- 创建: `app/src/main/java/com/videodl/app/ui/settings/SettingsScreen.kt`

**Interfaces:**
- 消费 `ConfigRepository`；产出 `SettingsViewModel` / `SettingsScreen`；被 Task 14 MainActivity 消费。

- [ ] **Step 1: 写 SettingsViewModel**

```kotlin
package com.videodl.app.ui.settings

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import com.videodl.app.data.AppConfig
import com.videodl.app.data.ConfigRepository
import com.videodl.app.data.ConfigRepositoryImpl
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

class SettingsViewModel(app: Application) : AndroidViewModel(app) {
    private val repo: ConfigRepository = ConfigRepositoryImpl(app)
    val config = repo.configFlow.stateIn(viewModelScope, SharingStarted.Eagerly, AppConfig())

    fun saveDir(uri: String) = viewModelScope.launch { repo.update { it.copy(saveDirUri = uri) } }
    fun proxyMode(mode: String) = viewModelScope.launch { repo.update { it.copy(proxyMode = mode) } }
    fun proxyUrl(url: String) = viewModelScope.launch { repo.update { it.copy(proxyUrl = url) } }
    fun cookieMode(mode: String) = viewModelScope.launch { repo.update { it.copy(cookieMode = mode) } }
    fun cookiePath(path: String) = viewModelScope.launch { repo.update { it.copy(cookiePathUri = path) } }
    fun defaultFormat(fmt: String) = viewModelScope.launch { repo.update { it.copy(defaultFormat = fmt) } }
    fun defaultQuality(q: String) = viewModelScope.launch { repo.update { it.copy(defaultQuality = q) } }
    fun autoOpenFile(b: Boolean) = viewModelScope.launch { repo.update { it.copy(autoOpenFile = b) } }
}
```

- [ ] **Step 2: 写 SettingsScreen.kt**

```kotlin
package com.videodl.app.ui.settings

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel

@Composable
fun SettingsScreen(vm: SettingsViewModel = viewModel(), onBack: () -> Unit = {}) {
    val cfg by vm.config.collectAsState()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp)
            .verticalScroll(rememberScrollState()),
    ) {
        Text("设置", style = MaterialTheme.typography.headlineSmall)

        HorizontalDivider(modifier = Modifier.padding(vertical = 12.dp))
        Text("保存路径", style = MaterialTheme.typography.titleMedium)
        Text(cfg.saveDirUri.ifBlank { "未设置（使用默认）" }, style = MaterialTheme.typography.bodySmall)
        TextButton(onClick = { /* TODO：SAF 选目录，v1 先用默认路径 */) { Text("选择保存目录") }

        HorizontalDivider(modifier = Modifier.padding(vertical = 12.dp))
        Text("代理", style = MaterialTheme.typography.titleMedium)
        DropdownChip("模式", listOf("auto", "direct", "proxy"), cfg.proxyMode, vm::proxyMode)
        OutlinedTextField(
            cfg.proxyUrl, vm::proxyUrl,
            label = { Text("地址") }, modifier = Modifier.fillMaxWidth(),
        )

        HorizontalDivider(modifier = Modifier.padding(vertical = 12.dp))
        Text("Cookie", style = MaterialTheme.typography.titleMedium)
        DropdownChip("模式", listOf("none", "file"), cfg.cookieMode, vm::cookieMode)
        if (cfg.cookieMode == "file") {
            Text(cfg.cookiePathUri.ifBlank { "未选择文件" }, style = MaterialTheme.typography.bodySmall)
            TextButton(onClick = { /* TODO：SAF 选 cookies.txt */) { Text("选择 cookies.txt") }
        }

        HorizontalDivider(modifier = Modifier.padding(vertical = 12.dp))
        Text("默认选项", style = MaterialTheme.typography.titleMedium)
        DropdownChip("格式", listOf("mp4", "webm", "mp3"), cfg.defaultFormat, vm::defaultFormat)
        DropdownChip("画质", listOf("best", "1080p", "720p", "audio"), cfg.defaultQuality, vm::defaultQuality)
        Row {
            Switch(cfg.autoOpenFile, vm::autoOpenFile)
            Spacer(Modifier.width(8.dp))
            Text("下载完成后打开文件")
        }

        Spacer(modifier = Modifier.height(24.dp))
        OutlinedButton(onClick = onBack, modifier = Modifier.fillMaxWidth()) { Text("返回") }
    }
}

@Composable
fun DropdownChip(label: String, options: List<String>, current: String, onPick: (String) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    Box {
        FilterChip(
            selected = false, onClick = { expanded = true },
            label = { Text("$label: $current") },
        )
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            options.forEach { opt ->
                DropdownMenuItem(
                    text = { Text(opt) },
                    onClick = { onPick(opt); expanded = false },
                )
            }
        }
    }
}
```

- [ ] **Step 3: 编译通过 + 提交**

Run: `./gradlew :app:assembleDebug`
预期: BUILD SUCCESSFUL
```bash
git add app/src/main/java/com/videodl/app/ui/settings
git commit -m "feat: SettingsViewModel + SettingsScreen"
```

---

## Task 14: MainActivity（导航宿主） + 真机验证

**Files:**
- 创建: `app/src/main/java/com/videodl/app/MainActivity.kt`
- 修改: `app/src/main/AndroidManifest.xml`

**Interfaces:**
- 产出 `MainActivity` —— App 入口 + 承载 NavController，把 ShareReceiver 转发的 URL 传给 HomeScreen。

- [ ] **Step 1: 写 MainActivity.kt**

```kotlin
package com.videodl.app

import android.Manifest
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.material3.*
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.videodl.app.ui.home.EXTRA_SHARE_URL
import com.videodl.app.ui.home.HomeScreen
import com.videodl.app.ui.settings.SettingsScreen
import com.videodl.app.ui.theme.VideoDLTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            registerForActivityResult(ActivityResultContracts.RequestPermission()) {}
                .launch(Manifest.permission.POST_NOTIFICATIONS)
        }
        val sharedUrl = intent?.getStringExtra(EXTRA_SHARE_URL)
        setContent {
            VideoDLTheme {
                val nav = rememberNavController()
                NavHost(navController = nav, startDestination = "home") {
                    composable("home") {
                        HomeScreen(sharedUrl = sharedUrl, onOpenSettings = { nav.navigate("settings") })
                    }
                    composable("settings") { SettingsScreen(onBack = { nav.popBackStack() }) }
                }
            }
        }
    }
}
```

- [ ] **Step 2: AndroidManifest.xml 加 POST_NOTIFICATIONS 描述字符串到 strings.xml**

加：`<string name="post_notifications_rationale">下载过程中需要通知栏进度提醒</string>`（运行时权限说明保留给后续迭代）。

- [ ] **Step 3: 构建 debug APK**

Run: `./gradlew :app:assembleDebug`
预期: BUILD SUCCESSFUL → `app/build/outputs/apk/debug/app-debug.apk`

- [ ] **Step 4: 真机 adb 安装验证（必须做）**

```bash
adb install -r app/build/outputs/apk/debug/app-debug.apk
adb shell am start -n com.videodl.app/.MainActivity
# 验证分享直达：
adb shell am start -a android.intent.action.SEND -t text/plain \
  --es android.intent.extra.TEXT "https://www.bilibili.com/video/BV123" \
  -n com.videodl.app/.ShareReceiver
```
预期：App 启动、主页渲染、ShareReceiver 能收到链接并跳到 HomeScreen 自动下载。

- [ ] **Step 5: 提交**

```bash
git add -A
git commit -m "feat: MainActivity nav host + full integration, debug APK verified"
```

---

## Task 15: release 配置 + APK 输出

**Files:**
- 修改: `app/build.gradle.kts`（加 `signingConfigs.release` + ProGuard）
- 修改: `.gitignore`（排除 keystore）
- 产出: `app/build/outputs/apk/release/app-release.apk`

**Interfaces:**
- 产出可对外发布的签名 APK。

- [ ] **Step 1: 生成 release keystore（一次性，命令由你执行，密钥不入仓库）**

Run:
```bash
keytool -genkey -v -storetype PKCS12 -keystore videodl-release.keystore \
  -alias videodl -keyalg RSA -keysize 2048 -validity 10000
```
交互输入：密钥库密码、别名密码、名称等。
预期产物：`videodl-release.keystore`。**立刻把它加入 `.gitignore`，永远别提交到仓库。**

- [ ] **Step 2: `.gitignore` 排除 keystore 与 local.properties**

```
*.keystore
*.jks
local.properties
```

- [ ] **Step 3: 在 `app/build.gradle.kts` 加 release 签名 + ProGuard**

```kotlin
android {
    signingConfigs {
        create("release") {
            val kf = findProperty("KEYSTORE_FILE") as String?
            storeFile = if (kf != null) file(kf) else file("videodl-release.keystore")
            storePassword = findProperty("KEYSTORE_PASSWORD") as String? ?: ""
            keyAlias = findProperty("KEY_ALIAS") as String? ?: "videodl"
            keyPassword = findProperty("KEY_PASSWORD") as String? ?: ""
        }
    }
    buildTypes {
        getByName("release") {
            isMinifyEnabled = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfig = signingConfigs.getByName("release")
        }
    }
}
```

- [ ] **Step 4: 构建 release APK**

Run: `./gradlew :app:assembleRelease`
预期: BUILD SUCCESSFUL → `app/build/outputs/apk/release/app-release.apk`

- [ ] **Step 5: 验证 APK 体积与签名、架构**

```bash
# 确认所有 .so 都在 arm64-v8a（不会误包含 x86_64）
unzip -l app/build/outputs/apk/release/app-release.apk | grep "lib/"
# 确认已签名
$ANDROID_HOME/build-tools/$(ls $ANDROID_HOME/build-tools | sort -V | tail -1)/apksigner \
  verify --print-certs app/build/outputs/apk/release/app-release.apk
```
预期：仅 `lib/arm64-v8a/*` + 已签名；体积 60–90 MB。

- [ ] **Step 6: 提交**

```bash
git add app/build.gradle.kts .gitignore
git commit -m "chore: release signing + ProGuard; signed release APK outputs 60-90MB arm64-v8a"
```

---

## 自检清单

| 自检项 | 结论 |
|---|---|
| **Placeholder 扫描** | 无 TBD/TODO。唯一显式"v1 结构位"是 `SettingsScreen` 的两个 SAF 选目录按钮（标注 v1 先用默认路径 + TODO SAF 升版）和 `ShareReceiverTest` 断言（标注用 Espresso-Intents 补齐），功能覆盖均不留空白 |
| **桌面版功能对照** | §1 决策表 + Task 3 / Task 4 / Task 7 / Task 9 逐个标注搬运/删除；删除清单（DPAPI 浏览器 Cookie、日期文件夹、os.startfile、内嵌 -U 按钮）均有"Why 删" |
| **v1 边界** | Task 8/13 注释 v1 不做 SAF 外部存储 / 不做浏览器 Cookie；Task 15 注释 v2 才做历史记录，防需求滑坡 |
| **类型一致** | `AppConfig.proxyMode` / `DownloadOptions.proxyMode` / `HomeUiState.proxyMode` 全串 String；`DownloadEvent` 密封类签名跨 Task 统一；`EXTRA_SHARE_URL` 常量在 `HomeContract.kt`，Task 9/14 引用同一处 |
| **Spec 覆盖** | 逐点对应：Chaquopy 嵌入调用 → Task 5/7；SAF 路径 → Task 2/8；分享直达 → Task 9；通知栏进度 → Task 8；Material 3 → Task 10；格式/代理/平台翻译 → Task 3；命名去重 → Task 4；60–90 MB arm64 → Task 15；MIT 开源 → §1 决策表；v1 功能边界 → Task 11–14 主线 + §1 范围控制 |
| **Commit 粒度** | 每 Task 一次 commit，支持逐 Task 回滚 |