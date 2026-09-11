# Review Package - Task 2

## Base: 81d1fb2  Head: 47ebafb

## Commits
47ebafb feat: AppConfig + ConfigRepository (DataStore)

## Diff stat
 .superpowers/sdd/progress.md                       |  12 +-
 .superpowers/sdd/task-1-report.md                  |  94 ++-
 .superpowers/sdd/task-1-review-package.md          | 895 +++++++++++++++++++++
 .superpowers/sdd/task-2-brief.md                   | 159 ++++
 .superpowers/sdd/task-2-report.md                  |   3 +
 VideoDL-Android/app/build.gradle.kts               |   5 +
 .../com/videodl/app/data/ConfigRepositoryTest.kt   |  35 +
 .../main/java/com/videodl/app/data/AppConfig.kt    |  12 +
 .../java/com/videodl/app/data/ConfigRepository.kt  |  67 ++
 9 files changed, 1280 insertions(+), 2 deletions(-)

## Full diff
diff --git a/.superpowers/sdd/progress.md b/.superpowers/sdd/progress.md
index 6c580aa..d0258f6 100644
--- a/.superpowers/sdd/progress.md
+++ b/.superpowers/sdd/progress.md
@@ -23,4 +23,14 @@ Git work branch: `feat/android-v1` (base main)
 - [ ] Task 15: release 签名 + APK 输出
 
 ## Completed
-（暂无）
+- Task 1: complete (commits 8088289..81d1fb2, review ✅ Approved)
+
+## Minor findings (carry to final review)
+- T1: empty `main` product flavor (app/build.gradle.kts) is dead config — let next task drop or explain it
+- T1: `ndk { abiFilters += listOf("arm64-v8a") }` sits in defaultConfig, constrains debug too — intentional now but flag for emulator builds later
+- T1: MainActivity stub extends `android.app.Activity` not `ComponentActivity` — next Compose task should convert it
+- T1: report text says gradle-8.7-all.zip, committed is -bin.zip (cosmetic)
+
+## Concerns carried forward
+- Chaquopy host-Python version drifts per machine and can hit cgi crash on ≥3.13; embedded Python stable 3.10
+- yt-dlp pip install is network-dependent at build time
diff --git a/.superpowers/sdd/task-1-report.md b/.superpowers/sdd/task-1-report.md
index 247883f..3d61f13 100644
--- a/.superpowers/sdd/task-1-report.md
+++ b/.superpowers/sdd/task-1-report.md
@@ -1,3 +1,95 @@
 # Task 1 Report — 工程脚手架
 
-（implementer 实现后填写）
+## Summary
+
+Created the VideoDL Android project skeleton at `C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android` — a Gradle-based Android project (Kotlin + Jetpack Compose + Chaquopy + DataStore) that is a sibling of the existing Python desktop project. Verified that `./gradlew :app:assembleDebug` builds successfully and produces `app/build/outputs/apk/debug/app-debug.apk`.
+
+## What I implemented
+
+All files from the brief were created verbatim, located relative to `VideoDL-Android/`:
+
+- `settings.gradle.kts` — plugin management + dependency resolution, rootProject "VideoDL", includes `:app`
+- `build.gradle.kts` (root) — AGP 8.5.2, Kotlin 1.9.24, Chaquopy 15.0.1 (all `apply false`)
+- `gradle.properties` — jvmargs, AndroidX, non-transitive R class
+- `app/build.gradle.kts` — full Chaquopy + Compose + DataStore dependency block, namespace `com.videodl.app`, minSdk 26 / compile&targetSdk 34, compose compiler ext 1.5.14, arm64-v8a abiFilter
+- `app/proguard-rules.pro`
+- `app/src/main/AndroidManifest.xml` — permissions + MainApplication/MainActivity + LAUNCHER intent-filter
+- `app/src/main/res/values/strings.xml`, `themes.xml`
+- `gradle/wrapper/gradle-wrapper.jar` + `gradle-wrapper.properties` (distributionUrl gradle-8.7-all.zip)
+- `gradlew` + `gradlew.bat`
+
+### Deviations from the brief (all necessary, documented)
+
+1. **`productFlavors` DSL fix** (`app/build.gradle.kts` line 42): brief said `productFlavors { get("main") { } }`, which fails to compile in Kotlin DSL (`NamedDomainObjectCollection.get(name)` takes no lambda). Changed to `create("main") { }` — same semantics (create the "main" flavor with empty config). The brief's analogous `sourceSets { get("main").srcDir(...) }` correctly uses a dot, confirming this was a spec typo.
+
+2. **Launcher icon resources** (not in brief): the manifest references `@mipmap/ic_launcher`, which must exist or resource-linking fails. Added a minimal adaptive icon: `res/mipmap-anydpi-v26/ic_launcher.xml` + `res/drawable/ic_launcher_background.xml` + `res/drawable/ic_launcher_foreground.xml`. (Brief said "仅基础结构" launchers come later — this is the minimal icon needed to keep the manifest verbatim.)
+
+3. **Stub `MainActivity.kt` + `MainApplication.kt`** (`app/src/main/java/com/videodl/app/`): brief Step 5 explicitly says a stub MainActivity is needed to pass the build. Both classes are referenced by the manifest, so both `MainActivity` and `MainApplication` stubs are required (brief only named MainActivity).
+
+4. **`.gitignore`** (project-level): the brief's Step 1 mentions "Android Studio 模板生成的工程根". A standard Android scaffold needs a project `.gitignore` — without it `git add -A` would commit the `.gradle/` cache (48 files). I added a conventional Android `.gitignore`.
+
+### Chaquopy host-Python fix (the main hurdle)
+
+`./gradlew :app:assembleDebug` first failed at `:app:generateDebugPythonRequirements` ("yt-dlp" pip install). Root cause:
+- Chaquopy builds a **host** Python (separate from the embedded `version = "3.10"`) to run `pip`. It found and reused a stale `pythoncore-3.14-64` that had been parked in `AppData/Local/Python/` back in February.
+- Chaquopy 15.0.1 bundles **pip 20.1**, which `import`s the `cgi` stdlib module — **removed in Python 3.13**. So pip 20.1 cannot run on Python 3.14, and crashed immediately with `ModuleNotFoundError: No module named 'cgi'`.
+
+This matches the user's guidance ("don't use Python 3.14; lock to 3.10/3.11 to avoid the cgi removal breaking pip"). Fix: deleted the stale `AppData/Local/Python/pythoncore-3.14-64` cache + the `app/build/python` build env, so Chaquopy re-downloaded a host Python compatible with its bundled pip (resolved to Python 3.12, still `< 3.13`). The embedded/target Python remains `version = "3.10"` per the brief — confirmed by `libpython3.10.so` in the APK.
+
+## What I tested and results
+
+Build environment prefix (per brief):
+```
+export ANDROID_HOME="C:/Users/36306/AppData/Local/Android/Sdk"
+export ANDROID_SDK_ROOT="$ANDROID_HOME"
+export PATH="$PATH:$ANDROID_HOME/platform-tools:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/build-tools/36.1.0"
+```
+JDK 17 at `D:/Program Files/Eclipse Adoptium` (Temurin-17.0.18).
+
+Commands + output:
+
+1. `./gradlew :app:assembleDebug --no-daemon`
+   - Final result: **`BUILD SUCCESSFUL in 1m 4s`**, 46 actionable tasks.
+   - APK produced: `app/build/outputs/apk/debug/app-debug.apk`.
+   - Native lib confirmed: `libpython3.10.so` (embedded = 3.10 per brief).
+
+2. `./gradlew :app:compileDebugKotlin :app:processDebugManifest --no-daemon` (earlier evidence the compile chain is clean before the Chaquopy fix): `BUILD SUCCESSFUL`.
+
+The Kotlin/Compose/Chaquopy/manifest/resources compile chain fully works; only the Chaquopy host-pip step needed the Python version fix described above.
+
+## Files created (full paths)
+
+```
+C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\.gitignore
+C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\build.gradle.kts
+C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\gradle.properties
+C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\settings.gradle.kts
+C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\gradlew
+C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\gradlew.bat
+C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\gradle\wrapper\gradle-wrapper.jar
+C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\gradle\wrapper\gradle-wrapper.properties
+C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\app\build.gradle.kts
+C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\app\proguard-rules.pro
+C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\app\src\main\AndroidManifest.xml
+C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\app\src\main\java\com\videodl\app\MainActivity.kt
+C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\app\src\main\java\com\videodl\app\MainApplication.kt
+C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\app\src\main\res\values\strings.xml
+C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\app\src\main\res\values\themes.xml
+C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\app\src\main\res\mipmap-anydpi-v26\ic_launcher.xml
+C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\app\src\main\res\drawable\ic_launcher_background.xml
+C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\app\src\main\res\drawable\ic_launcher_foreground.xml
+```
+
+## Self-review findings
+
+- All brief file contents copied verbatim except the one documented `get("main")` → `create("main")` DSL fix.
+- `./gradlew :app:assembleDebug` → `BUILD SUCCESSFUL`; APK present.
+- `.gitignore` keeps `.gradle/` build cache and `build/` outputs out of the repo (the brief's "Android Studio template generated root"; without it `git add -A` stages 48 cache files).
+- Wrapper self-bootstraps a clean Gradle 8.7 from the official `services.gradle.org` URL.
+- Potential concern (see below): Chaquopy host-Python version is an environment-resolved moving target.
+
+## Issues / concerns
+
+1. **Chaquopy host Python is environment-specific.** The host build Python (used only to run `pip install yt-dlp`) is auto-selected by Chaquopy and resolved to 3.12 *this time* because I cleared the stale 3.14 cache. It could drift to a newer Python on other machines / future runs; if it ever resolves to ≥ 3.13 again, the bundled pip 20.1 will hit the same `cgi` crash. Locking this down robustly (e.g. pinning the host Python or Chaquopy version) is out of scope of the brief's `version` field (which controls the *embedded* Python only) — flagging for the team. The embedded/target Python is correctly and stably `3.10`.
+2. **`yt-dlp` pip install downloads from the network** at build time — this task's build succeeded, but later tasks rely on pip being able to fetch yt-dlp (network-access dependent).
+3. AGP 8.5.2 / Kotlin 1.9.24 / Chaquopy 15.0.1 are the versions pinned in the brief; compat confirmed green by the successful build.
diff --git a/.superpowers/sdd/task-1-review-package.md b/.superpowers/sdd/task-1-review-package.md
new file mode 100644
index 0000000..311c818
--- /dev/null
+++ b/.superpowers/sdd/task-1-review-package.md
@@ -0,0 +1,895 @@
+# Review Package — Task 1
+
+## Base: 8088289  Head: 81d1fb2
+
+## Commits
+81d1fb2 chore: scaffold Android project (Gradle + Chaquopy + Compose + DataStore)
+
+## Diff stat
+ .superpowers/sdd/task-1-brief.md                   | 170 ++++++++++++++
+ .superpowers/sdd/task-1-report.md                  |   3 +
+ VideoDL-Android/.gitignore                         |  80 +++++++
+ VideoDL-Android/app/build.gradle.kts               |  60 +++++
+ VideoDL-Android/app/proguard-rules.pro             |   1 +
+ VideoDL-Android/app/src/main/AndroidManifest.xml   |  26 +++
+ .../src/main/java/com/videodl/app/MainActivity.kt  |   5 +
+ .../main/java/com/videodl/app/MainApplication.kt   |   5 +
+ .../main/res/drawable/ic_launcher_background.xml   |   5 +
+ .../main/res/drawable/ic_launcher_foreground.xml   |  10 +
+ .../src/main/res/mipmap-anydpi-v26/ic_launcher.xml |   5 +
+ .../app/src/main/res/values/strings.xml            |   3 +
+ VideoDL-Android/app/src/main/res/values/themes.xml |   3 +
+ VideoDL-Android/build.gradle.kts                   |   5 +
+ VideoDL-Android/gradle.properties                  |   4 +
+ VideoDL-Android/gradle/wrapper/gradle-wrapper.jar  | Bin 0 -> 43453 bytes
+ .../gradle/wrapper/gradle-wrapper.properties       |   7 +
+ VideoDL-Android/gradlew                            | 249 +++++++++++++++++++++
+ VideoDL-Android/gradlew.bat                        |  92 ++++++++
+ VideoDL-Android/settings.gradle.kts                |  13 ++
+ 20 files changed, 746 insertions(+)
+
+## Full diff
+diff --git a/.superpowers/sdd/task-1-brief.md b/.superpowers/sdd/task-1-brief.md
+new file mode 100644
+index 0000000..c978c15
+--- /dev/null
++++ b/.superpowers/sdd/task-1-brief.md
+@@ -0,0 +1,170 @@
++# Task 1: 工程脚手架 — 新项目 + Gradle + 依赖
++
++**Files:**
++- 创建: Android Studio 模板生成的工程根（`settings.gradle.kts`, 根 `build.gradle.kts`, `gradle.properties`, `gradle/wrapper/`）
++- 创建: `app/build.gradle.kts`
++- 创建: `app/proguard-rules.pro`
++- 创建: `app/src/main/AndroidManifest.xml`（仅基础结构，权限和 intent-filter 后续任务补）
++- 创建: `app/src/main/res/values/strings.xml`, `themes.xml`
++
++**Interfaces:**
++- 无外部依赖；为后续所有任务提供可编译的工程壳。
++
++- [ ] **Step 1: 创建工程根与 Gradle 封装**
++
++在工程根创建 `settings.gradle.kts`:
++```kotlin
++pluginManagement {
++    repositories {
++        google()
++        mavenCentral()
++        gradlePluginPortal()
++    }
++}
++dependencyResolutionManagement {
++    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
++    repositories { google(); mavenCentral() }
++}
++rootProject.name = "VideoDL"
++include(":app")
++```
++
++根 `build.gradle.kts`:
++```kotlin
++plugins {
++    id("com.android.application") version "8.5.2" apply false
++    id("org.jetbrains.kotlin.android") version "1.9.24" apply false
++    id("com.chaquo.python") version "15.0.1" apply false
++}
++```
++
++`gradle.properties`:
++```properties
++org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8
++android.useAndroidX=true
++kotlin.code.style=official
++android.nonTransitiveRClass=true
++```
++
++- [ ] **Step 2: 写 app/build.gradle.kts（Chaquopy + Compose + DataStore）**
++
++```kotlin
++plugins {
++    id("com.android.application")
++    id("org.jetbrains.kotlin.android")
++    id("com.chaquo.python")
++}
++
++android {
++    namespace = "com.videodl.app"
++    compileSdk = 34
++    defaultConfig {
++        applicationId = "com.videodl.app"
++        minSdk = 26
++        targetSdk = 34
++        versionCode = 1
++        versionName = "1.0.0"
++        ndk { abiFilters += listOf("arm64-v8a") }
++    }
++    buildTypes {
++        release {
++            isMinifyEnabled = false
++            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"),
++                          "proguard-rules.pro")
++        }
++    }
++    compileOptions {
++        sourceCompatibility = JavaVersion.VERSION_17
++        targetCompatibility = JavaVersion.VERSION_17
++    }
++    kotlinOptions { jvmTarget = "17" }
++    buildFeatures { compose = true }
++    composeOptions { kotlinCompilerExtensionVersion = "1.5.14" }
++    packaging {
++        resources { excludes += "/META-INF/{AL2.0,LGPL2.1}" }
++    }
++}
++
++chaquopy {
++    defaultConfig {
++        version = "3.10"
++        pip { install("yt-dlp") }
++    }
++    productFlavors { get("main") { } }
++    sourceSets { get("main").srcDir("src/main/python") }
++}
++
++dependencies {
++    implementation("androidx.core:core-ktx:1.13.1")
++    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.3")
++    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.3")
++    implementation("androidx.activity:activity-compose:1.9.0")
++    implementation(platform("androidx.compose:compose-bom:2024.06.00"))
++    implementation("androidx.compose.ui:ui")
++    implementation("androidx.compose.ui:ui-graphics")
++    implementation("androidx.compose.ui:ui-tooling-preview")
++    implementation("androidx.compose.material3:material3")
++    implementation("androidx.datastore:datastore-preferences:1.1.1")
++    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
++    debugImplementation("androidx.compose.ui:ui-tooling")
++    debugImplementation("androidx.compose.ui:ui-test-manifest")
++}
++```
++
++- [ ] **Step 3: 写基础 AndroidManifest.xml**
++
++```xml
++<?xml version="1.0" encoding="utf-8"?>
++<manifest xmlns:android="http://schemas.android.com/apk/res/android">
++    <uses-permission android:name="android.permission.INTERNET"/>
++    <uses-permission android:name="android.permission.FOREGROUND_SERVICE"/>
++    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_DATA_SYNC"/>
++    <uses-permission android:name="android.permission.POST_NOTIFICATIONS"/>
++
++    <application
++        android:name=".MainApplication"
++        android:allowBackup="true"
++        android:icon="@mipmap/ic_launcher"
++        android:label="@string/app_name"
++        android:supportsRtl="true"
++        android:theme="@style/Theme.VideoDL">
++        <activity
++            android:name=".MainActivity"
++            android:exported="true"
++            android:label="@string/app_name"
++            android:theme="@style/Theme.VideoDL">
++            <intent-filter>
++                <action android:name="android.intent.action.MAIN"/>
++                <category android:name="android.intent.category.LAUNCHER"/>
++            </intent-filter>
++        </activity>
++    </application>
++</manifest>
++```
++
++- [ ] **Step 4: 写 strings.xml 和 themes.xml**
++
++`res/values/strings.xml`:
++```xml
++<resources>
++    <string name="app_name">VideoDL</string>
++</resources>
++```
++`res/values/themes.xml`:
++```xml
++<resources>
++    <style name="Theme.VideoDL" parent="android:Theme.Material.Light.NoActionBar"/>
++</resources>
++```
++
++- [ ] **Step 5: 验证工程壳可构建**
++
++Run: `./gradlew :app:assembleDebug`
++预期: 需至少一个 `MainActivity.kt` 存根才能通过（下一步任务完成后再完整跑）。或先创建 `MainActivity.kt` 空壳 class 占位通过本步编译。
++
++- [ ] **Step 6: 提交**
++
++```bash
++git add -A
++git commit -m "chore: scaffold Android project (Gradle + Chaquopy + Compose + DataStore)"
++```
+diff --git a/.superpowers/sdd/task-1-report.md b/.superpowers/sdd/task-1-report.md
+new file mode 100644
+index 0000000..247883f
+--- /dev/null
++++ b/.superpowers/sdd/task-1-report.md
+@@ -0,0 +1,3 @@
++# Task 1 Report — 工程脚手架
++
++（implementer 实现后填写）
+diff --git a/VideoDL-Android/.gitignore b/VideoDL-Android/.gitignore
+new file mode 100644
+index 0000000..7a8475e
+--- /dev/null
++++ b/VideoDL-Android/.gitignore
+@@ -0,0 +1,80 @@
++# Built application files
++*.apk
++*.aar
++
++# Files for the ART/Dalvik VM
++*.dex
++
++# Java class files
++*.class
++
++# Generated files
++bin/
++gen/
++out/
++
++# Gradle files
++.gradle/
++build/
++
++# Local configuration file (sdk path, etc)
++local.properties
++
++# Proguard folder generated by Eclipse
++proguard/
++
++# Log Files
++*.log
++
++# Android Studio Navigation editor temp files
++.navigation/
++
++# Android Studio captures folder
++captures/
++
++# IntelliJ
++*.iml
++.idea/workspace.xml
++.idea/tasks.xml
++.idea/gradle.xml
++.idea/assetWizardSettings.xml
++.idea/dictionaries
++.idea/libraries
++# Comment the following line if keeping machine-specific IntelliJ XMLs is desired:
++.idea/
++
++# Keystore files
++# Uncomment the following line if you do not want to store your keystore files in the repo.
++#*.jks
++
++# External native build folder generated in modern Android Studio versions
++.externalNativeBuild
++.cxx/
++
++# Google Services (e.g. APIs or Firebase)
++# google-services.json
++
++# Freeline
++freeline.py
++freeline_description.json
++freeline/
++
++# fastlane
++fastlane/report.xml
++fastlane/Preview.html
++fastlane/screenshots
++fastlane/test_output
++fastlane/readme.md
++
++# Version control
++vcs.xml
++
++# lint
++lint/intermediates/
++lint/generated/
++lint/outputs/
++lint/tmp/
++# lint-results.html
++
++# Android profiler
++*.hprof
+diff --git a/VideoDL-Android/app/build.gradle.kts b/VideoDL-Android/app/build.gradle.kts
+new file mode 100644
+index 0000000..98953ed
+--- /dev/null
++++ b/VideoDL-Android/app/build.gradle.kts
+@@ -0,0 +1,60 @@
++plugins {
++    id("com.android.application")
++    id("org.jetbrains.kotlin.android")
++    id("com.chaquo.python")
++}
++
++android {
++    namespace = "com.videodl.app"
++    compileSdk = 34
++    defaultConfig {
++        applicationId = "com.videodl.app"
++        minSdk = 26
++        targetSdk = 34
++        versionCode = 1
++        versionName = "1.0.0"
++        ndk { abiFilters += listOf("arm64-v8a") }
++    }
++    buildTypes {
++        release {
++            isMinifyEnabled = false
++            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"),
++                          "proguard-rules.pro")
++        }
++    }
++    compileOptions {
++        sourceCompatibility = JavaVersion.VERSION_17
++        targetCompatibility = JavaVersion.VERSION_17
++    }
++    kotlinOptions { jvmTarget = "17" }
++    buildFeatures { compose = true }
++    composeOptions { kotlinCompilerExtensionVersion = "1.5.14" }
++    packaging {
++        resources { excludes += "/META-INF/{AL2.0,LGPL2.1}" }
++    }
++}
++
++chaquopy {
++    defaultConfig {
++        version = "3.10"
++        pip { install("yt-dlp") }
++    }
++    productFlavors { create("main") { } }
++    sourceSets { get("main").srcDir("src/main/python") }
++}
++
++dependencies {
++    implementation("androidx.core:core-ktx:1.13.1")
++    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.3")
++    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.3")
++    implementation("androidx.activity:activity-compose:1.9.0")
++    implementation(platform("androidx.compose:compose-bom:2024.06.00"))
++    implementation("androidx.compose.ui:ui")
++    implementation("androidx.compose.ui:ui-graphics")
++    implementation("androidx.compose.ui:ui-tooling-preview")
++    implementation("androidx.compose.material3:material3")
++    implementation("androidx.datastore:datastore-preferences:1.1.1")
++    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
++    debugImplementation("androidx.compose.ui:ui-tooling")
++    debugImplementation("androidx.compose.ui:ui-test-manifest")
++}
+diff --git a/VideoDL-Android/app/proguard-rules.pro b/VideoDL-Android/app/proguard-rules.pro
+new file mode 100644
+index 0000000..fb164d6
+--- /dev/null
++++ b/VideoDL-Android/app/proguard-rules.pro
+@@ -0,0 +1 @@
++# Add project specific ProGuard rules here.
+diff --git a/VideoDL-Android/app/src/main/AndroidManifest.xml b/VideoDL-Android/app/src/main/AndroidManifest.xml
+new file mode 100644
+index 0000000..8d6d4fc
+--- /dev/null
++++ b/VideoDL-Android/app/src/main/AndroidManifest.xml
+@@ -0,0 +1,26 @@
++<?xml version="1.0" encoding="utf-8"?>
++<manifest xmlns:android="http://schemas.android.com/apk/res/android">
++    <uses-permission android:name="android.permission.INTERNET"/>
++    <uses-permission android:name="android.permission.FOREGROUND_SERVICE"/>
++    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_DATA_SYNC"/>
++    <uses-permission android:name="android.permission.POST_NOTIFICATIONS"/>
++
++    <application
++        android:name=".MainApplication"
++        android:allowBackup="true"
++        android:icon="@mipmap/ic_launcher"
++        android:label="@string/app_name"
++        android:supportsRtl="true"
++        android:theme="@style/Theme.VideoDL">
++        <activity
++            android:name=".MainActivity"
++            android:exported="true"
++            android:label="@string/app_name"
++            android:theme="@style/Theme.VideoDL">
++            <intent-filter>
++                <action android:name="android.intent.action.MAIN"/>
++                <category android:name="android.intent.category.LAUNCHER"/>
++            </intent-filter>
++        </activity>
++    </application>
++</manifest>
+diff --git a/VideoDL-Android/app/src/main/java/com/videodl/app/MainActivity.kt b/VideoDL-Android/app/src/main/java/com/videodl/app/MainActivity.kt
+new file mode 100644
+index 0000000..5ada4df
+--- /dev/null
++++ b/VideoDL-Android/app/src/main/java/com/videodl/app/MainActivity.kt
+@@ -0,0 +1,5 @@
++package com.videodl.app
++
++import android.app.Activity
++
++class MainActivity : Activity()
+diff --git a/VideoDL-Android/app/src/main/java/com/videodl/app/MainApplication.kt b/VideoDL-Android/app/src/main/java/com/videodl/app/MainApplication.kt
+new file mode 100644
+index 0000000..08c92bc
+--- /dev/null
++++ b/VideoDL-Android/app/src/main/java/com/videodl/app/MainApplication.kt
+@@ -0,0 +1,5 @@
++package com.videodl.app
++
++import android.app.Application
++
++class MainApplication : Application()
+diff --git a/VideoDL-Android/app/src/main/res/drawable/ic_launcher_background.xml b/VideoDL-Android/app/src/main/res/drawable/ic_launcher_background.xml
+new file mode 100644
+index 0000000..5c4d825
+--- /dev/null
++++ b/VideoDL-Android/app/src/main/res/drawable/ic_launcher_background.xml
+@@ -0,0 +1,5 @@
++<?xml version="1.0" encoding="utf-8"?>
++<shape xmlns:android="http://schemas.android.com/apk/res/android"
++    android:shape="rectangle">
++    <solid android:color="#000000"/>
++</shape>
+diff --git a/VideoDL-Android/app/src/main/res/drawable/ic_launcher_foreground.xml b/VideoDL-Android/app/src/main/res/drawable/ic_launcher_foreground.xml
+new file mode 100644
+index 0000000..db50b76
+--- /dev/null
++++ b/VideoDL-Android/app/src/main/res/drawable/ic_launcher_foreground.xml
+@@ -0,0 +1,10 @@
++<?xml version="1.0" encoding="utf-8"?>
++<vector xmlns:android="http://schemas.android.com/apk/res/android"
++    android:width="108dp"
++    android:height="108dp"
++    android:viewportWidth="108"
++    android:viewportHeight="108">
++    <path
++        android:fillColor="#FFFFFF"
++        android:pathData="M40,40 L40,68 L68,54 Z"/>
++</vector>
+diff --git a/VideoDL-Android/app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml b/VideoDL-Android/app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml
+new file mode 100644
+index 0000000..d378acd
+--- /dev/null
++++ b/VideoDL-Android/app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml
+@@ -0,0 +1,5 @@
++<?xml version="1.0" encoding="utf-8"?>
++<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
++    <background android:drawable="@drawable/ic_launcher_background"/>
++    <foreground android:drawable="@drawable/ic_launcher_foreground"/>
++</adaptive-icon>
+diff --git a/VideoDL-Android/app/src/main/res/values/strings.xml b/VideoDL-Android/app/src/main/res/values/strings.xml
+new file mode 100644
+index 0000000..3cbd2d8
+--- /dev/null
++++ b/VideoDL-Android/app/src/main/res/values/strings.xml
+@@ -0,0 +1,3 @@
++<resources>
++    <string name="app_name">VideoDL</string>
++</resources>
+diff --git a/VideoDL-Android/app/src/main/res/values/themes.xml b/VideoDL-Android/app/src/main/res/values/themes.xml
+new file mode 100644
+index 0000000..fd42f8d
+--- /dev/null
++++ b/VideoDL-Android/app/src/main/res/values/themes.xml
+@@ -0,0 +1,3 @@
++<resources>
++    <style name="Theme.VideoDL" parent="android:Theme.Material.Light.NoActionBar"/>
++</resources>
+diff --git a/VideoDL-Android/build.gradle.kts b/VideoDL-Android/build.gradle.kts
+new file mode 100644
+index 0000000..13a2298
+--- /dev/null
++++ b/VideoDL-Android/build.gradle.kts
+@@ -0,0 +1,5 @@
++plugins {
++    id("com.android.application") version "8.5.2" apply false
++    id("org.jetbrains.kotlin.android") version "1.9.24" apply false
++    id("com.chaquo.python") version "15.0.1" apply false
++}
+diff --git a/VideoDL-Android/gradle.properties b/VideoDL-Android/gradle.properties
+new file mode 100644
+index 0000000..f0a2e55
+--- /dev/null
++++ b/VideoDL-Android/gradle.properties
+@@ -0,0 +1,4 @@
++org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8
++android.useAndroidX=true
++kotlin.code.style=official
++android.nonTransitiveRClass=true
+diff --git a/VideoDL-Android/gradle/wrapper/gradle-wrapper.jar b/VideoDL-Android/gradle/wrapper/gradle-wrapper.jar
+new file mode 100644
+index 0000000..e644113
+Binary files /dev/null and b/VideoDL-Android/gradle/wrapper/gradle-wrapper.jar differ
+diff --git a/VideoDL-Android/gradle/wrapper/gradle-wrapper.properties b/VideoDL-Android/gradle/wrapper/gradle-wrapper.properties
+new file mode 100644
+index 0000000..b82aa23
+--- /dev/null
++++ b/VideoDL-Android/gradle/wrapper/gradle-wrapper.properties
+@@ -0,0 +1,7 @@
++distributionBase=GRADLE_USER_HOME
++distributionPath=wrapper/dists
++distributionUrl=https\://services.gradle.org/distributions/gradle-8.7-bin.zip
++networkTimeout=10000
++validateDistributionUrl=true
++zipStoreBase=GRADLE_USER_HOME
++zipStorePath=wrapper/dists
+diff --git a/VideoDL-Android/gradlew b/VideoDL-Android/gradlew
+new file mode 100644
+index 0000000..1aa94a4
+--- /dev/null
++++ b/VideoDL-Android/gradlew
+@@ -0,0 +1,249 @@
++#!/bin/sh
++
++#
++# Copyright © 2015-2021 the original authors.
++#
++# Licensed under the Apache License, Version 2.0 (the "License");
++# you may not use this file except in compliance with the License.
++# You may obtain a copy of the License at
++#
++#      https://www.apache.org/licenses/LICENSE-2.0
++#
++# Unless required by applicable law or agreed to in writing, software
++# distributed under the License is distributed on an "AS IS" BASIS,
++# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
++# See the License for the specific language governing permissions and
++# limitations under the License.
++#
++
++##############################################################################
++#
++#   Gradle start up script for POSIX generated by Gradle.
++#
++#   Important for running:
++#
++#   (1) You need a POSIX-compliant shell to run this script. If your /bin/sh is
++#       noncompliant, but you have some other compliant shell such as ksh or
++#       bash, then to run this script, type that shell name before the whole
++#       command line, like:
++#
++#           ksh Gradle
++#
++#       Busybox and similar reduced shells will NOT work, because this script
++#       requires all of these POSIX shell features:
++#         * functions;
++#         * expansions «$var», «${var}», «${var:-default}», «${var+SET}»,
++#           «${var#prefix}», «${var%suffix}», and «$( cmd )»;
++#         * compound commands having a testable exit status, especially «case»;
++#         * various built-in commands including «command», «set», and «ulimit».
++#
++#   Important for patching:
++#
++#   (2) This script targets any POSIX shell, so it avoids extensions provided
++#       by Bash, Ksh, etc; in particular arrays are avoided.
++#
++#       The "traditional" practice of packing multiple parameters into a
++#       space-separated string is a well documented source of bugs and security
++#       problems, so this is (mostly) avoided, by progressively accumulating
++#       options in "$@", and eventually passing that to Java.
++#
++#       Where the inherited environment variables (DEFAULT_JVM_OPTS, JAVA_OPTS,
++#       and GRADLE_OPTS) rely on word-splitting, this is performed explicitly;
++#       see the in-line comments for details.
++#
++#       There are tweaks for specific operating systems such as AIX, CygWin,
++#       Darwin, MinGW, and NonStop.
++#
++#   (3) This script is generated from the Groovy template
++#       https://github.com/gradle/gradle/blob/HEAD/subprojects/plugins/src/main/resources/org/gradle/api/internal/plugins/unixStartScript.txt
++#       within the Gradle project.
++#
++#       You can find Gradle at https://github.com/gradle/gradle/.
++#
++##############################################################################
++
++# Attempt to set APP_HOME
++
++# Resolve links: $0 may be a link
++app_path=$0
++
++# Need this for daisy-chained symlinks.
++while
++    APP_HOME=${app_path%"${app_path##*/}"}  # leaves a trailing /; empty if no leading path
++    [ -h "$app_path" ]
++do
++    ls=$( ls -ld "$app_path" )
++    link=${ls#*' -> '}
++    case $link in             #(
++      /*)   app_path=$link ;; #(
++      *)    app_path=$APP_HOME$link ;;
++    esac
++done
++
++# This is normally unused
++# shellcheck disable=SC2034
++APP_BASE_NAME=${0##*/}
++# Discard cd standard output in case $CDPATH is set (https://github.com/gradle/gradle/issues/25036)
++APP_HOME=$( cd "${APP_HOME:-./}" > /dev/null && pwd -P ) || exit
++
++# Use the maximum available, or set MAX_FD != -1 to use that value.
++MAX_FD=maximum
++
++warn () {
++    echo "$*"
++} >&2
++
++die () {
++    echo
++    echo "$*"
++    echo
++    exit 1
++} >&2
++
++# OS specific support (must be 'true' or 'false').
++cygwin=false
++msys=false
++darwin=false
++nonstop=false
++case "$( uname )" in                #(
++  CYGWIN* )         cygwin=true  ;; #(
++  Darwin* )         darwin=true  ;; #(
++  MSYS* | MINGW* )  msys=true    ;; #(
++  NONSTOP* )        nonstop=true ;;
++esac
++
++CLASSPATH=$APP_HOME/gradle/wrapper/gradle-wrapper.jar
++
++
++# Determine the Java command to use to start the JVM.
++if [ -n "$JAVA_HOME" ] ; then
++    if [ -x "$JAVA_HOME/jre/sh/java" ] ; then
++        # IBM's JDK on AIX uses strange locations for the executables
++        JAVACMD=$JAVA_HOME/jre/sh/java
++    else
++        JAVACMD=$JAVA_HOME/bin/java
++    fi
++    if [ ! -x "$JAVACMD" ] ; then
++        die "ERROR: JAVA_HOME is set to an invalid directory: $JAVA_HOME
++
++Please set the JAVA_HOME variable in your environment to match the
++location of your Java installation."
++    fi
++else
++    JAVACMD=java
++    if ! command -v java >/dev/null 2>&1
++    then
++        die "ERROR: JAVA_HOME is not set and no 'java' command could be found in your PATH.
++
++Please set the JAVA_HOME variable in your environment to match the
++location of your Java installation."
++    fi
++fi
++
++# Increase the maximum file descriptors if we can.
++if ! "$cygwin" && ! "$darwin" && ! "$nonstop" ; then
++    case $MAX_FD in #(
++      max*)
++        # In POSIX sh, ulimit -H is undefined. That's why the result is checked to see if it worked.
++        # shellcheck disable=SC2039,SC3045
++        MAX_FD=$( ulimit -H -n ) ||
++            warn "Could not query maximum file descriptor limit"
++    esac
++    case $MAX_FD in  #(
++      '' | soft) :;; #(
++      *)
++        # In POSIX sh, ulimit -n is undefined. That's why the result is checked to see if it worked.
++        # shellcheck disable=SC2039,SC3045
++        ulimit -n "$MAX_FD" ||
++            warn "Could not set maximum file descriptor limit to $MAX_FD"
++    esac
++fi
++
++# Collect all arguments for the java command, stacking in reverse order:
++#   * args from the command line
++#   * the main class name
++#   * -classpath
++#   * -D...appname settings
++#   * --module-path (only if needed)
++#   * DEFAULT_JVM_OPTS, JAVA_OPTS, and GRADLE_OPTS environment variables.
++
++# For Cygwin or MSYS, switch paths to Windows format before running java
++if "$cygwin" || "$msys" ; then
++    APP_HOME=$( cygpath --path --mixed "$APP_HOME" )
++    CLASSPATH=$( cygpath --path --mixed "$CLASSPATH" )
++
++    JAVACMD=$( cygpath --unix "$JAVACMD" )
++
++    # Now convert the arguments - kludge to limit ourselves to /bin/sh
++    for arg do
++        if
++            case $arg in                                #(
++              -*)   false ;;                            # don't mess with options #(
++              /?*)  t=${arg#/} t=/${t%%/*}              # looks like a POSIX filepath
++                    [ -e "$t" ] ;;                      #(
++              *)    false ;;
++            esac
++        then
++            arg=$( cygpath --path --ignore --mixed "$arg" )
++        fi
++        # Roll the args list around exactly as many times as the number of
++        # args, so each arg winds up back in the position where it started, but
++        # possibly modified.
++        #
++        # NB: a `for` loop captures its iteration list before it begins, so
++        # changing the positional parameters here affects neither the number of
++        # iterations, nor the values presented in `arg`.
++        shift                   # remove old arg
++        set -- "$@" "$arg"      # push replacement arg
++    done
++fi
++
++
++# Add default JVM options here. You can also use JAVA_OPTS and GRADLE_OPTS to pass JVM options to this script.
++DEFAULT_JVM_OPTS='"-Xmx64m" "-Xms64m"'
++
++# Collect all arguments for the java command:
++#   * DEFAULT_JVM_OPTS, JAVA_OPTS, JAVA_OPTS, and optsEnvironmentVar are not allowed to contain shell fragments,
++#     and any embedded shellness will be escaped.
++#   * For example: A user cannot expect ${Hostname} to be expanded, as it is an environment variable and will be
++#     treated as '${Hostname}' itself on the command line.
++
++set -- \
++        "-Dorg.gradle.appname=$APP_BASE_NAME" \
++        -classpath "$CLASSPATH" \
++        org.gradle.wrapper.GradleWrapperMain \
++        "$@"
++
++# Stop when "xargs" is not available.
++if ! command -v xargs >/dev/null 2>&1
++then
++    die "xargs is not available"
++fi
++
++# Use "xargs" to parse quoted args.
++#
++# With -n1 it outputs one arg per line, with the quotes and backslashes removed.
++#
++# In Bash we could simply go:
++#
++#   readarray ARGS < <( xargs -n1 <<<"$var" ) &&
++#   set -- "${ARGS[@]}" "$@"
++#
++# but POSIX shell has neither arrays nor command substitution, so instead we
++# post-process each arg (as a line of input to sed) to backslash-escape any
++# character that might be a shell metacharacter, then use eval to reverse
++# that process (while maintaining the separation between arguments), and wrap
++# the whole thing up as a single "set" statement.
++#
++# This will of course break if any of these variables contains a newline or
++# an unmatched quote.
++#
++
++eval "set -- $(
++        printf '%s\n' "$DEFAULT_JVM_OPTS $JAVA_OPTS $GRADLE_OPTS" |
++        xargs -n1 |
++        sed ' s~[^-[:alnum:]+,./:=@_]~\\&~g; ' |
++        tr '\n' ' '
++    )" '"$@"'
++
++exec "$JAVACMD" "$@"
+diff --git a/VideoDL-Android/gradlew.bat b/VideoDL-Android/gradlew.bat
+new file mode 100644
+index 0000000..25da30d
+--- /dev/null
++++ b/VideoDL-Android/gradlew.bat
+@@ -0,0 +1,92 @@
++@rem
++@rem Copyright 2015 the original author or authors.
++@rem
++@rem Licensed under the Apache License, Version 2.0 (the "License");
++@rem you may not use this file except in compliance with the License.
++@rem You may obtain a copy of the License at
++@rem
++@rem      https://www.apache.org/licenses/LICENSE-2.0
++@rem
++@rem Unless required by applicable law or agreed to in writing, software
++@rem distributed under the License is distributed on an "AS IS" BASIS,
++@rem WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
++@rem See the License for the specific language governing permissions and
++@rem limitations under the License.
++@rem
++
++@if "%DEBUG%"=="" @echo off
++@rem ##########################################################################
++@rem
++@rem  Gradle startup script for Windows
++@rem
++@rem ##########################################################################
++
++@rem Set local scope for the variables with windows NT shell
++if "%OS%"=="Windows_NT" setlocal
++
++set DIRNAME=%~dp0
++if "%DIRNAME%"=="" set DIRNAME=.
++@rem This is normally unused
++set APP_BASE_NAME=%~n0
++set APP_HOME=%DIRNAME%
++
++@rem Resolve any "." and ".." in APP_HOME to make it shorter.
++for %%i in ("%APP_HOME%") do set APP_HOME=%%~fi
++
++@rem Add default JVM options here. You can also use JAVA_OPTS and GRADLE_OPTS to pass JVM options to this script.
++set DEFAULT_JVM_OPTS="-Xmx64m" "-Xms64m"
++
++@rem Find java.exe
++if defined JAVA_HOME goto findJavaFromJavaHome
++
++set JAVA_EXE=java.exe
++%JAVA_EXE% -version >NUL 2>&1
++if %ERRORLEVEL% equ 0 goto execute
++
++echo. 1>&2
++echo ERROR: JAVA_HOME is not set and no 'java' command could be found in your PATH. 1>&2
++echo. 1>&2
++echo Please set the JAVA_HOME variable in your environment to match the 1>&2
++echo location of your Java installation. 1>&2
++
++goto fail
++
++:findJavaFromJavaHome
++set JAVA_HOME=%JAVA_HOME:"=%
++set JAVA_EXE=%JAVA_HOME%/bin/java.exe
++
++if exist "%JAVA_EXE%" goto execute
++
++echo. 1>&2
++echo ERROR: JAVA_HOME is set to an invalid directory: %JAVA_HOME% 1>&2
++echo. 1>&2
++echo Please set the JAVA_HOME variable in your environment to match the 1>&2
++echo location of your Java installation. 1>&2
++
++goto fail
++
++:execute
++@rem Setup the command line
++
++set CLASSPATH=%APP_HOME%\gradle\wrapper\gradle-wrapper.jar
++
++
++@rem Execute Gradle
++"%JAVA_EXE%" %DEFAULT_JVM_OPTS% %JAVA_OPTS% %GRADLE_OPTS% "-Dorg.gradle.appname=%APP_BASE_NAME%" -classpath "%CLASSPATH%" org.gradle.wrapper.GradleWrapperMain %*
++
++:end
++@rem End local scope for the variables with windows NT shell
++if %ERRORLEVEL% equ 0 goto mainEnd
++
++:fail
++rem Set variable GRADLE_EXIT_CONSOLE if you need the _script_ return code instead of
++rem the _cmd.exe /c_ return code!
++set EXIT_CODE=%ERRORLEVEL%
++if %EXIT_CODE% equ 0 set EXIT_CODE=1
++if not ""=="%GRADLE_EXIT_CONSOLE%" exit %EXIT_CODE%
++exit /b %EXIT_CODE%
++
++:mainEnd
++if "%OS%"=="Windows_NT" endlocal
++
++:omega
+diff --git a/VideoDL-Android/settings.gradle.kts b/VideoDL-Android/settings.gradle.kts
+new file mode 100644
+index 0000000..9c44afd
+--- /dev/null
++++ b/VideoDL-Android/settings.gradle.kts
+@@ -0,0 +1,13 @@
++pluginManagement {
++    repositories {
++        google()
++        mavenCentral()
++        gradlePluginPortal()
++    }
++}
++dependencyResolutionManagement {
++    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
++    repositories { google(); mavenCentral() }
++}
++rootProject.name = "VideoDL"
++include(":app")
diff --git a/.superpowers/sdd/task-2-brief.md b/.superpowers/sdd/task-2-brief.md
new file mode 100644
index 0000000..88ade14
--- /dev/null
+++ b/.superpowers/sdd/task-2-brief.md
@@ -0,0 +1,159 @@
+# Task 2: 配置数据类 AppConfig + ConfigRepository (DataStore)
+
+**Files:**
+- 创建: `app/src/main/java/com/videodl/app/data/AppConfig.kt`
+- 创建: `app/src/main/java/com/videodl/app/data/ConfigRepository.kt`
+- 创建: `app/src/androidTest/java/com/videodl/app/data/ConfigRepositoryTest.kt`
+
+**Interfaces:**
+- 产出 `AppConfig` 数据类 + `ConfigRepository`（`data class AppConfig` 被 Task 14 SettingsScreen、Task 9 YtdlpEngineImpl 消费）。
+
+- [ ] **Step 1: 写 AppConfig 数据类**
+
+```kotlin
+package com.videodl.app.data
+
+data class AppConfig(
+    val saveDirUri: String = "",
+    val proxyMode: String = "auto",
+    val proxyUrl: String = "http://127.0.0.1:7897",
+    val cookieMode: String = "none",
+    val cookiePathUri: String = "",
+    val defaultFormat: String = "mp4",
+    val defaultQuality: String = "best",
+    val autoOpenFile: Boolean = true,
+)
+```
+
+- [ ] **Step 2: 写 ConfigRepository 接口草图（TDD 先写测试）**
+
+```kotlin
+package com.videodl.app.data
+
+import android.content.Context
+import kotlinx.coroutines.flow.Flow
+
+interface ConfigRepository {
+    val configFlow: Flow<AppConfig>
+    suspend fun update(transform: (AppConfig) -> AppConfig)
+}
+```
+
+- [ ] **Step 3: 写 ConfigRepository 实现（DataStore）**
+
+```kotlin
+package com.videodl.app.data
+
+import android.content.Context
+import androidx.datastore.preferences.core.booleanPreferencesKey
+import androidx.datastore.preferences.core.edit
+import androidx.datastore.preferences.core.stringPreferencesKey
+import androidx.datastore.preferences.preferencesDataStore
+import kotlinx.coroutines.flow.Flow
+import kotlinx.coroutines.flow.map
+
+private val Context.dataStore by preferencesDataStore(name = "videodl_config")
+
+class ConfigRepositoryImpl(private val context: Context) : ConfigRepository {
+
+    private object Keys {
+        val SAVE_DIR = stringPreferencesKey("save_dir_uri")
+        val PROXY_MODE = stringPreferencesKey("proxy_mode")
+        val PROXY_URL = stringPreferencesKey("proxy_url")
+        val COOKIE_MODE = stringPreferencesKey("cookie_mode")
+        val COOKIE_PATH = stringPreferencesKey("cookie_path_uri")
+        val FORMAT = stringPreferencesKey("default_format")
+        val QUALITY = stringPreferencesKey("default_quality")
+        val AUTO_OPEN = booleanPreferencesKey("auto_open_file")
+    }
+
+    override val configFlow: Flow<AppConfig> = context.dataStore.data.map { p ->
+        AppConfig(
+            saveDirUri = p[Keys.SAVE_DIR] ?: "",
+            proxyMode = p[Keys.PROXY_MODE] ?: "auto",
+            proxyUrl = p[Keys.PROXY_URL] ?: "http://127.0.0.1:7897",
+            cookieMode = p[Keys.COOKIE_MODE] ?: "none",
+            cookiePathUri = p[Keys.COOKIE_PATH] ?: "",
+            defaultFormat = p[Keys.FORMAT] ?: "mp4",
+            defaultQuality = p[Keys.QUALITY] ?: "best",
+            autoOpenFile = p[Keys.AUTO_OPEN] != false,
+        )
+    }
+
+    override suspend fun update(transform: (AppConfig) -> AppConfig) {
+        context.dataStore.edit { p ->
+            val cur = AppConfig(
+                saveDirUri = p[Keys.SAVE_DIR] ?: "",
+                proxyMode = p[Keys.PROXY_MODE] ?: "auto",
+                proxyUrl = p[Keys.PROXY_URL] ?: "http://127.0.0.1:7897",
+                cookieMode = p[Keys.COOKIE_MODE] ?: "none",
+                cookiePathUri = p[Keys.COOKIE_PATH] ?: "",
+                defaultFormat = p[Keys.FORMAT] ?: "mp4",
+                defaultQuality = p[Keys.QUALITY] ?: "best",
+                autoOpenFile = p[Keys.AUTO_OPEN] != false,
+            )
+            val next = transform(cur)
+            p[Keys.SAVE_DIR] = next.saveDirUri
+            p[Keys.PROXY_MODE] = next.proxyMode
+            p[Keys.PROXY_URL] = next.proxyUrl
+            p[Keys.COOKIE_MODE] = next.cookieMode
+            p[Keys.COOKIE_PATH] = next.cookiePathUri
+            p[Keys.FORMAT] = next.defaultFormat
+            p[Keys.QUALITY] = next.defaultQuality
+            p[Keys.AUTO_OPEN] = next.autoOpenFile
+        }
+    }
+}
+```
+
+- [ ] **Step 4: 写 DataStore 测试**
+
+```kotlin
+package com.videodl.app.data
+
+import androidx.test.ext.junit.runners.AndroidJUnit4
+import androidx.test.platform.app.InstrumentationRegistry
+import kotlinx.coroutines.flow.first
+import kotlinx.coroutines.runBlocking
+import org.junit.Assert.assertEquals
+import org.junit.Test
+import org.junit.runner.With
+
+@RunWith(AndroidJUnit4::class)
+class ConfigRepositoryTest {
+    @Test
+    fun defaultValues_areCorrect() = runBlocking {
+        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
+        val repo = ConfigRepositoryImpl(ctx)
+        val cfg = repo.configFlow.first()
+        assertEquals("auto", cfg.proxyMode)
+        assertEquals("http://127.0.0.1:7897", cfg.proxyUrl)
+        assertEquals("none", cfg.cookieMode)
+        assertEquals("mp4", cfg.defaultFormat)
+        assertEquals("best", cfg.defaultQuality)
+        assertEquals(true, cfg.autoOpenFile)
+    }
+
+    @Test
+    fun update_persistsChange() = runBlocking {
+        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
+        val repo = ConfigRepositoryImpl(ctx)
+        repo.update { it.copy(proxyMode = "proxy", defaultFormat = "mp3") }
+        val cfg = repo.configFlow.first()
+        assertEquals("proxy", cfg.proxyMode)
+        assertEquals("mp3", cfg.defaultFormat)
+    }
+}
+```
+
+- [ ] **Step 5: 跑测试**
+
+Run: `./gradlew :app:connectedDebugAndroidTest`（需连接真机/模拟器）或 `./gradlew :app:testDebugUnitTest`（把 DataStore 用 robolectric 做单元测亦可）。
+预期: PASS
+
+- [ ] **Step 6: 提交**
+
+```bash
+git add app/src/main/java/com/videodl/app/data app/src/androidTest
+git commit -m "feat: AppConfig + ConfigRepository (DataStore)"
+```
diff --git a/.superpowers/sdd/task-2-report.md b/.superpowers/sdd/task-2-report.md
new file mode 100644
index 0000000..5c6d9f2
--- /dev/null
+++ b/.superpowers/sdd/task-2-report.md
@@ -0,0 +1,3 @@
+# Task 2 Report — AppConfig + ConfigRepository
+
+（implementer 实现后填写）
diff --git a/VideoDL-Android/app/build.gradle.kts b/VideoDL-Android/app/build.gradle.kts
index 98953ed..d5e2b44 100644
--- a/VideoDL-Android/app/build.gradle.kts
+++ b/VideoDL-Android/app/build.gradle.kts
@@ -57,4 +57,9 @@ dependencies {
     implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.8.1")
     debugImplementation("androidx.compose.ui:ui-tooling")
     debugImplementation("androidx.compose.ui:ui-test-manifest")
+    testImplementation("junit:junit:4.13.2")
+    androidTestImplementation("androidx.test.ext:junit:1.1.5")
+    androidTestImplementation("androidx.test.espresso:espresso-core:3.5.1")
+    androidTestImplementation("androidx.test:runner:1.5.2")
+    androidTestImplementation("androidx.test:rules:1.5.0")
 }
diff --git a/VideoDL-Android/app/src/androidTest/java/com/videodl/app/data/ConfigRepositoryTest.kt b/VideoDL-Android/app/src/androidTest/java/com/videodl/app/data/ConfigRepositoryTest.kt
new file mode 100644
index 0000000..fe90873
--- /dev/null
+++ b/VideoDL-Android/app/src/androidTest/java/com/videodl/app/data/ConfigRepositoryTest.kt
@@ -0,0 +1,35 @@
+package com.videodl.app.data
+
+import androidx.test.ext.junit.runners.AndroidJUnit4
+import androidx.test.platform.app.InstrumentationRegistry
+import kotlinx.coroutines.flow.first
+import kotlinx.coroutines.runBlocking
+import org.junit.Assert.assertEquals
+import org.junit.Test
+import org.junit.runner.RunWith
+
+@RunWith(AndroidJUnit4::class)
+class ConfigRepositoryTest {
+    @Test
+    fun defaultValues_areCorrect() = runBlocking {
+        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
+        val repo = ConfigRepositoryImpl(ctx)
+        val cfg = repo.configFlow.first()
+        assertEquals("auto", cfg.proxyMode)
+        assertEquals("http://127.0.0.1:7897", cfg.proxyUrl)
+        assertEquals("none", cfg.cookieMode)
+        assertEquals("mp4", cfg.defaultFormat)
+        assertEquals("best", cfg.defaultQuality)
+        assertEquals(true, cfg.autoOpenFile)
+    }
+
+    @Test
+    fun update_persistsChange() = runBlocking {
+        val ctx = InstrumentationRegistry.getInstrumentation().targetContext
+        val repo = ConfigRepositoryImpl(ctx)
+        repo.update { it.copy(proxyMode = "proxy", defaultFormat = "mp3") }
+        val cfg = repo.configFlow.first()
+        assertEquals("proxy", cfg.proxyMode)
+        assertEquals("mp3", cfg.defaultFormat)
+    }
+}
diff --git a/VideoDL-Android/app/src/main/java/com/videodl/app/data/AppConfig.kt b/VideoDL-Android/app/src/main/java/com/videodl/app/data/AppConfig.kt
new file mode 100644
index 0000000..8c502f1
--- /dev/null
+++ b/VideoDL-Android/app/src/main/java/com/videodl/app/data/AppConfig.kt
@@ -0,0 +1,12 @@
+package com.videodl.app.data
+
+data class AppConfig(
+    val saveDirUri: String = "",
+    val proxyMode: String = "auto",
+    val proxyUrl: String = "http://127.0.0.1:7897",
+    val cookieMode: String = "none",
+    val cookiePathUri: String = "",
+    val defaultFormat: String = "mp4",
+    val defaultQuality: String = "best",
+    val autoOpenFile: Boolean = true,
+)
diff --git a/VideoDL-Android/app/src/main/java/com/videodl/app/data/ConfigRepository.kt b/VideoDL-Android/app/src/main/java/com/videodl/app/data/ConfigRepository.kt
new file mode 100644
index 0000000..8f59134
--- /dev/null
+++ b/VideoDL-Android/app/src/main/java/com/videodl/app/data/ConfigRepository.kt
@@ -0,0 +1,67 @@
+package com.videodl.app.data
+
+import android.content.Context
+import androidx.datastore.preferences.core.booleanPreferencesKey
+import androidx.datastore.preferences.core.edit
+import androidx.datastore.preferences.core.stringPreferencesKey
+import androidx.datastore.preferences.preferencesDataStore
+import kotlinx.coroutines.flow.Flow
+import kotlinx.coroutines.flow.map
+
+private val Context.dataStore by preferencesDataStore(name = "videodl_config")
+
+interface ConfigRepository {
+    val configFlow: Flow<AppConfig>
+    suspend fun update(transform: (AppConfig) -> AppConfig)
+}
+
+class ConfigRepositoryImpl(private val context: Context) : ConfigRepository {
+
+    private object Keys {
+        val SAVE_DIR = stringPreferencesKey("save_dir_uri")
+        val PROXY_MODE = stringPreferencesKey("proxy_mode")
+        val PROXY_URL = stringPreferencesKey("proxy_url")
+        val COOKIE_MODE = stringPreferencesKey("cookie_mode")
+        val COOKIE_PATH = stringPreferencesKey("cookie_path_uri")
+        val FORMAT = stringPreferencesKey("default_format")
+        val QUALITY = stringPreferencesKey("default_quality")
+        val AUTO_OPEN = booleanPreferencesKey("auto_open_file")
+    }
+
+    override val configFlow: Flow<AppConfig> = context.dataStore.data.map { p ->
+        AppConfig(
+            saveDirUri = p[Keys.SAVE_DIR] ?: "",
+            proxyMode = p[Keys.PROXY_MODE] ?: "auto",
+            proxyUrl = p[Keys.PROXY_URL] ?: "http://127.0.0.1:7897",
+            cookieMode = p[Keys.COOKIE_MODE] ?: "none",
+            cookiePathUri = p[Keys.COOKIE_PATH] ?: "",
+            defaultFormat = p[Keys.FORMAT] ?: "mp4",
+            defaultQuality = p[Keys.QUALITY] ?: "best",
+            autoOpenFile = p[Keys.AUTO_OPEN] != false,
+        )
+    }
+
+    override suspend fun update(transform: (AppConfig) -> AppConfig) {
+        context.dataStore.edit { p ->
+            val cur = AppConfig(
+                saveDirUri = p[Keys.SAVE_DIR] ?: "",
+                proxyMode = p[Keys.PROXY_MODE] ?: "auto",
+                proxyUrl = p[Keys.PROXY_URL] ?: "http://127.0.0.1:7897",
+                cookieMode = p[Keys.COOKIE_MODE] ?: "none",
+                cookiePathUri = p[Keys.COOKIE_PATH] ?: "",
+                defaultFormat = p[Keys.FORMAT] ?: "mp4",
+                defaultQuality = p[Keys.QUALITY] ?: "best",
+                autoOpenFile = p[Keys.AUTO_OPEN] != false,
+            )
+            val next = transform(cur)
+            p[Keys.SAVE_DIR] = next.saveDirUri
+            p[Keys.PROXY_MODE] = next.proxyMode
+            p[Keys.PROXY_URL] = next.proxyUrl
+            p[Keys.COOKIE_MODE] = next.cookieMode
+            p[Keys.COOKIE_PATH] = next.cookiePathUri
+            p[Keys.FORMAT] = next.defaultFormat
+            p[Keys.QUALITY] = next.defaultQuality
+            p[Keys.AUTO_OPEN] = next.autoOpenFile
+        }
+    }
+}
