# Task 4 Report: 文件命名去重（FileRepository 核心逻辑）

## Status: DONE

## Pre-flight
- `testImplementation("junit:junit:4.13.2")` present in `app/build.gradle.kts` (line 60) — no change needed.
- `AppConfig.kt` + `ConfigRepository.kt` confirmed present in `app/src/main/java/com/videodl/app/data/`.
- Branch: `feat/android-v1`.

## Files created
- `C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\app\src\main\java\com\videodl\app\data\FileRepository.kt` (object `Naming`: `nextFilePath` + `sanitize`)
- `C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\app\src\test\java\com\videodl\app\data\FileRepositoryTest.kt` (class `NamingTest`, 3 tests)

## Implementation
Step 1 `Naming` and Step 2 `NamingTest` copied verbatim from the brief. Same package `com.videodl.app.data`. No deviations.

## TDD evidence (RED → GREEN)
Build/env prefix used for every gradle call:
```
export ANDROID_HOME="C:/Users/36306/AppData/Local/Android/Sdk"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
```

### Initial GREEN (impl + tests written together per brief Step 1→2)
```
./gradlew :app:testDebugUnitTest --tests "com.videodl.app.data.NamingTest" --no-daemon
... BUILD SUCCESSFUL, 27 actionable tasks: 7 executed, 20 up-to-date
```
JUnit XML: `tests="3" skipped="0" failures="0" errors="0"` — `firstAvailable_noSuffix`, `conflict_addsSuffix`, `sanitize_replacesForbiddenChars` all pass.

### Induced RED (impl deliberately broken: `var idx = startAt + 1`)
```
com.videodl.app.data.NamingTest > firstAvailable_noSuffix FAILED
    org.junit.ComparisonFailure at FileRepositoryTest.kt:8
3 tests completed, 1 failed
BUILD FAILED in 16s
```

### Restored GREEN (impl reverted to original `var idx = startAt`)
```
BUILD SUCCESSFUL in 16s
```

## Commit
- `a186872` feat: file naming + sanitize

## Deviations
None. Brief code copied verbatim.

## Concerns
None. Chaquopy Python-version warning (`Python 3.10 may have fewer packages`) is a pre-existing configuration warning, unrelated to this task.
