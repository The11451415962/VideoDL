# Task 3 Report — format/platform/proxy logic（implementer 实现后填写）

## 实现内容

将桌面版 `video_downloader.py` 的三个函数 1:1 翻译为 Kotlin：
- `detect_platform(url)` → `Platform.detect(url)`
- `resolve_proxy(config, url)` → `ProxyResolver.resolve(proxyMode, proxyUrl, url)`
- `resolve_format_string(fmt, quality, platform)` → `Format.resolve(fmt, quality, platform)`

产出三个 `object`（Platform / ProxyResolver / Format），合在一个源文件里，供 Task 9 DownloadOptions 与 Task 11 HomeViewModel 消费。

源文件逐行对照 Python，确保完全等价：
- `Platform.detect`：`url.contains(xxx, true)` 对应 Python 的 `url.lower()` 子串匹配，平台顺序 YouTube → Bilibili → 抖音 → 未知。
- `ProxyResolver.resolve`：三个分支 exact-match `direct`/`proxy`/`auto`，auto 分支仅 YouTube 返回代理（对应 Python 的 `config.get` 方式，Kotlin 版把 proxyUrl 作为参数传入，语义等价）。
- `Format.resolve`：
  - mp3 / audio → `["-f", "bestaudio/best", "--audio-format", "mp3"]`
  - YouTube webm 分支：三档 quality 的 selector 字符串（含 `[ext=webm]`、`[height<=1080/720]`）与 Python 完全一致
  - YouTube mp4 分支：同上，`[ext=mp4]`/`[ext=m4a]` 一致
  - Bilibili / 其他：不限 ext，`height<=1080/720` + best 兜底，与 Python 完全一致

## TDD 证据（RED → GREEN）

### RED（首次跑测试，预期失败）

命令：
```
./gradlew :app:testDebugUnitTest --tests "com.videodl.app.engine.*" --no-daemon
```

结果：`10 tests completed, 2 failed`
- `FormatTest.youtube_best_mp4` — `AssertionError` at `ProxyResolverTest.kt:13`（即 `FormatTest.kt` 第 13 行）
- `FormatTest.bilibili_noExtFilter` — `AssertionError` at `ProxyResolverTest.kt:19`

根因：测试里 `List.contains(x)` 是**元素相等**判断，不是子串查找。`Format.resolve` 返回的是 `["-f", "<selector>", "--merge-output-format", "mp4"]`，selector 是单个元素，所以：
- `r.contains("[ext=mp4]")` 永远为 false（列表里没有等于 `"[ext=mp4]"` 的元素）
- `r.contains("height<=1080")` 同理

注意：**这是测试断言的 bug，不是生产代码的 bug**。同一测试 `bilibili_noExtFilter` 的第一行用的就是 `r.joinToString().contains("ext=")`，写法正确且通过，说明 `Format.resolve` 产出的数据本身是对的；后面两行用了错误的 `r.contains()` 形式。生产代码对照 Python 源码确认一字不差，不需要改。

### GREEN（修测试断言后）

把 `FormatTest` 里两处错误的 `r.contains(...)` 改成 `r.joinToString().contains(...)`（与该测试自己第一行的正确写法风格一致），生产代码零改动。

命令：
```
./gradlew :app:testDebugUnitTest --tests "com.videodl.app.engine.*" --no-daemon
```

结果：`BUILD SUCCESSFUL in 16s`，`10 tests completed, 0 failed`

## 偏差与原因

- **偏差**：`FormatTest` 两个断言从 `r.contains(x)` 改为 `r.joinToString().contains(x)`。
- **原因**：测试代码本身有 bug — `List.contains` 做的是元素相等比较，而断言意图是「selector 字符串是否包含某子串」。修复后的写法与该测试自己第一行 (`assertFalse(r.joinToString().contains("ext="))`) 完全一致，测试意图不变。生产代码 `FormatResolver.kt` 未动。
- build.gradle.kts 的 `testImplementation("junit:junit:4.13.2")` 已存在（第 60 行），无需新增。无其它偏差。

## 创建的文件（全路径）

- `C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\app\src\main\java\com\videodl\app\engine\FormatResolver.kt` — 三个 object（Platform / ProxyResolver / Format）
- `C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\app\src\test\java\com\videodl\app\engine\FormatResolverTest.kt` — `PlatformTest` + `ProxyResolverTest`
- `C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android\app\src\test\java\com\videodl\app\engine\ProxyResolverTest.kt` — `FormatTest`

目录树按要求创建：
- `app/src/main/java/com/videodl/app/engine/`
- `app/src/test/java/com/videodl/app/engine/`（JVM unit test，非 androidTest）

## 自检发现

- 生产代码与 Python `video_downloader.py` 第 142、155、175 行的三个函数对照，selector 字符串、ext 限定、height 分支、分支顺序完全等价。无 drift。
- `ProxyResolver.resolve` 签名把 `proxyUrl` 作为参数（Python 是 `config.get`），由调用方传入，对 Task 9/11 的接入方透明，语义等价。
- 包名全部 `com.videodl.app.engine`，与 brief 一致。
- git status：commit 仅含 `app/src/main/java/com/videodl/app/engine` 与 `app/src/test`，与 brief Step 4 的 `git add` 一致。未提交 `.superpowers/` 下的 brief/report 等产物。

## 关注点 / 后续接入提醒

- Task 9 DownloadOptions / Task 11 HomeViewModel 接入 `Platform.detect`、`ProxyResolver.resolve`、`Format.resolve` 时，`Format.resolve` 返回的是 `List<String>`（参数 key/value 对），调用方要把它解包进 yt-dlp 命令行，不要二次包装。
- `ProxyResolver.resolve` 调用方负责把 config 的 `proxy_url` 字符串取出来传进去；auto 分支只识别 YouTube（与桌面版行为一致）。
- 测试修复属于「让测试正确反映既有的正确实现」，并非 TDD 的「改生产代码」环节；生产代码从未被改动过。
