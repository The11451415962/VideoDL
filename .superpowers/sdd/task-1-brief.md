# Task 1: 工程脚手架 — 新项目 + Gradle + 依赖

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
