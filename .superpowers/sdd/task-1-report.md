# Task 1 Report — 工程脚手架

## Summary

Created the VideoDL Android project skeleton at `C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android` — a Gradle-based Android project (Kotlin + Jetpack Compose + Chaquopy + DataStore) that is a sibling of the existing Python desktop project. Verified that `./gradlew :app:assembleDebug` builds successfully and produces `app/build/outputs/apk/debug/app-debug.apk`.

## What I implemented

All files from the brief were created verbatim, located relative to `VideoDL-Android/`:

- `settings.gradle.kts` — plugin management + dependency resolution, rootProject "VideoDL", includes `:app`
- `build.gradle.kts` (root) — AGP 8.5.2, Kotlin 1.9.24, Chaquopy 15.0.1 (all `apply false`)
- `gradle.properties` — jvmargs, AndroidX, non-transitive R class
- `app/build.gradle.kts` — full Chaquopy + Compose + DataStore dependency block, namespace `com.videodl.app`, minSdk 26 / compile&targetSdk 34, compose compiler ext 1.5.14, arm64-v8a abiFilter
- `app/proguard-rules.pro`
- `app/src/main/AndroidManifest.xml` — permissions + MainApplication/MainActivity + LAUNCHER intent-filter
- `app/src/main/res/values/strings.xml`, `themes.xml`
- `gradle/wrapper/gradle-wrapper.jar` + `gradle-wrapper.properties` (distributionUrl gradle-8.7-all.zip)
- `gradlew` + `gradlew.bat`

### Deviations from the brief (all necessary, documented)

1. **`productFlavors` DSL fix** (`app/build.gradle.kts` line 42): brief said `productFlavors { get("main") { } }`, which fails to compile in Kotlin DSL (`NamedDomainObjectCollection.get(name)` takes no lambda). Changed to `create("main") { }` — same semantics (create the "main" flavor with empty config). The brief's analogous `sourceSets { get("main").srcDir(...) }` correctly uses a dot, confirming this was a spec typo.

2. **Launcher icon resources** (not in brief): the manifest references `@mipmap/ic_launcher`, which must exist or resource-linking fails. Added a minimal adaptive icon: `res/mipmap-anydpi-v26/ic_launcher.xml` + `res/drawable/ic_launcher_background.xml` + `res/drawable/ic_launcher_foreground.xml`. (Brief said "仅基础结构" launchers come later — this is the minimal icon needed to keep the manifest verbatim.)

3. **Stub `MainActivity.kt` + `MainApplication.kt`** (`app/src/main/java/com/videodl/app/`): brief Step 5 explicitly says a stub MainActivity is needed to pass the build. Both classes are referenced by the manifest, so both `MainActivity` and `MainApplication` stubs are required (brief only named MainActivity).

4. **`.gitignore`** (project-level): the brief's Step 1 mentions "Android Studio 模板生成的工程根". A standard Android scaffold needs a project `.gitignore` — without it `git add -A` would commit the `.gradle/` cache (48 files). I added a conventional Android `.gitignore`.

### Chaquopy host-Python fix (the main hurdle)

`./gradlew :app:assembleDebug` first failed at `:app:generateDebugPythonRequirements` ("yt-dlp" pip install). Root cause:
- Chaquopy builds a **host** Python (separate from the embedded `version = "3.10"`) to run `pip`. It found and reused a stale `pythoncore-3.14-64` that had been parked in `AppData/Local/Python/` back in February.
- Chaquopy 15.0.1 bundles **pip 20.1**, which `import`s the `cgi` stdlib module — **removed in Python 3.13**. So pip 20.1 cannot run on Python 3.14, and crashed immediately with `ModuleNotFoundError: No module named 'cgi'`.

This matches the user's guidance ("don't use Python 3.14; lock to 3.10/3.11 to avoid the cgi removal breaking pip"). Fix: deleted the stale `AppData/Local/Python/pythoncore-3.14-64` cache + the `app/build/python` build env, so Chaquopy re-downloaded a host Python compatible with its bundled pip (resolved to Python 3.12, still `< 3.13`). The embedded/target Python remains `version = "3.10"` per the brief — confirmed by `libpython3.10.so` in the APK.

## What I tested and results

Build environment prefix (per brief):
```
export ANDROID_HOME="C:/Users/36306/AppData/Local/Android/Sdk"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export PATH="$PATH:$ANDROID_HOME/platform-tools:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/build-tools/36.1.0"
```
JDK 17 at `D:/Program Files/Eclipse Adoptium` (Temurin-17.0.18).

Commands + output:

1. `./gradlew :app:assembleDebug --no-daemon`
   - Final result: **`BUILD SUCCESSFUL in 1m 4s`**, 46 actionable tasks.
   - APK produced: `app/build/outputs/apk/debug/app-debug.apk`.
   - Native lib confirmed: `libpython3.10.so` (embedded = 3.10 per brief).

2. `./gradlew :app:compileDebugKotlin :app:processDebugManifest --no-daemon` (earlier evidence the compile chain is clean before the Chaquopy fix): `BUILD SUCCESSFUL`.

The Kotlin/Compose/Chaquopy/manifest/resources compile chain fully works; only the Chaquopy host-pip step needed the Python version fix described above.

## Files created (full paths)

```
C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\.gitignore
C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\build.gradle.kts
C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\gradle.properties
C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\settings.gradle.kts
C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\gradlew
C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\gradlew.bat
C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\gradle\wrapper\gradle-wrapper.jar
C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\gradle\wrapper\gradle-wrapper.properties
C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\app\build.gradle.kts
C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\app\proguard-rules.pro
C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\app\src\main\AndroidManifest.xml
C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\app\src\main\java\com\videodl\app\MainActivity.kt
C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\app\src\main\java\com\videodl\app\MainApplication.kt
C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\app\src\main\res\values\strings.xml
C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\app\src\main\res\values\themes.xml
C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\app\src\main\res\mipmap-anydpi-v26\ic_launcher.xml
C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\app\src\main\res\drawable\ic_launcher_background.xml
C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\app\src\main\res\drawable\ic_launcher_foreground.xml
```

## Self-review findings

- All brief file contents copied verbatim except the one documented `get("main")` → `create("main")` DSL fix.
- `./gradlew :app:assembleDebug` → `BUILD SUCCESSFUL`; APK present.
- `.gitignore` keeps `.gradle/` build cache and `build/` outputs out of the repo (the brief's "Android Studio template generated root"; without it `git add -A` stages 48 cache files).
- Wrapper self-bootstraps a clean Gradle 8.7 from the official `services.gradle.org` URL.
- Potential concern (see below): Chaquopy host-Python version is an environment-resolved moving target.

## Issues / concerns

1. **Chaquopy host Python is environment-specific.** The host build Python (used only to run `pip install yt-dlp`) is auto-selected by Chaquopy and resolved to 3.12 *this time* because I cleared the stale 3.14 cache. It could drift to a newer Python on other machines / future runs; if it ever resolves to ≥ 3.13 again, the bundled pip 20.1 will hit the same `cgi` crash. Locking this down robustly (e.g. pinning the host Python or Chaquopy version) is out of scope of the brief's `version` field (which controls the *embedded* Python only) — flagging for the team. The embedded/target Python is correctly and stably `3.10`.
2. **`yt-dlp` pip install downloads from the network** at build time — this task's build succeeded, but later tasks rely on pip being able to fetch yt-dlp (network-access dependent).
3. AGP 8.5.2 / Kotlin 1.9.24 / Chaquopy 15.0.1 are the versions pinned in the brief; compat confirmed green by the successful build.
