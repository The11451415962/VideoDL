# SDD Progress — VideoDL Android (feat/android-v1)

Plan: `docs/superpowers/plans/2026-07-20-videodl-android.md`（勾选框已与本文同步）
Android project root: `C:\Users\36306\Desktop\shipinxiazaiqi\VideoDL-Android`
Git work branch: `feat/android-v1`（base main）

> 台账最后更新时间：2026-09-13。Task 1–15 全部完成，唯一留白是 Task 15 Step 1
> （生成 release 密钥库）—— 那一步需要用户自己执行并保管密码。

## Task 状态

| Task | 内容 | 状态 | 备注 |
|---|---|---|---|
| 1 | 工程脚手架 | ✅ | |
| 2 | AppConfig + ConfigRepository (DataStore) | ✅ | 见下方遗留小项 |
| 3 | 格式/代理/平台逻辑翻译 | ✅ | |
| 4 | 文件命名去重 | ✅ | |
| 5 | Python yt-dlp 桥脚本 | ✅ | Python 侧无 JVM 测试 |
| 6 | 引擎接口 + DownloadOptions | ✅ | |
| 7 | YtdlpEngineImpl (Chaquopy) | ✅ | |
| 8 | 前台 DownloadService + 通知 + FileRepository | ✅ | |
| 9 | 系统分享直达 ShareReceiver | ✅ | |
| 10 | Material 3 主题 | ✅ | |
| 11 | HomeViewModel 状态机 | ✅ | |
| 12 | HomeScreen Compose UI | ✅ | |
| 13 | SettingsViewModel + SettingsScreen | ✅ | |
| 14 | MainActivity 导航宿主 + 真机验证 | ✅ | 真机跑通，见下 |
| 15 | release 签名 + APK 输出 | ⚠️ 部分 | 签名配置已接通并实测签名成功；**用户自己的密钥库还没生成** |

## 测试（权威统计，来自 build/test-results）

JVM 单测 **49 个用例 / 0 失败 / 0 跳过**，分布在 8 个文件、10 个测试类
（类名与文件名不一致，一个文件里可能有多个类）：

| 测试类 | 用例数 | 所在文件 |
|---|---|---|
| `DownloadHistoryCodecTest` | 6 | DownloadHistoryCodecTest.kt |
| `NamingTest` | 3 | FileRepositoryTest.kt |
| `FileRepositoryPureTest` | 4 | FileRepositoryTest.kt |
| `FormatOptionTest` | 10 | FormatOptionTest.kt |
| `PlatformTest` | 4 | FormatResolverTest.kt |
| `ProxyResolverTest` | 3 | FormatResolverTest.kt |
| `FormatTest` | 4 | ProxyResolverTest.kt |
| `ProgressTextTest` | 4 | ProgressTextTest.kt |
| `HomeUiStateTest` | 4 | HomeViewModelTest.kt |
| `SplitFormatsTest` | 7 | SplitFormatsTest.kt |

```bash
cd VideoDL-Android
./gradlew.bat :app:testDebugUnitTest --console=plain
```

`androidTest`（`ShareReceiverTest`、`ConfigRepositoryTest`）**从未在真机上跑过** ——
review verdict 应为 ⚠️ unverified-runtime（环境限制），不要当它通过。

## 真机验证状态（PJC110 / OPPO / Android 15 / arm64-v8a）

**已验证**
- 真机安装运行、真实下载、用 ffprobe 验证产物确实是 h264 + aac
- 队列行为有 logcat 实证（`queued` / `dispatch next from queue` / `queue empty`）
- 分享入口触发下载（不依赖界面点击）

**未验证**
- 视觉微调（`3b8f3b0`）之后**没有拿到 App 界面的截图**：下完视频会自动打开播放器抢屏，
  随后手机锁屏，截不到界面。所以那一轮的观感改动只经过了代码层面检查。
- 通知栏的「取消」按钮没有用手点过（adb 点不到，Service 非 exported）
- release 包**没有装到真机上跑过**（只验证到"能构建、能签名、ABI 与体积正常"）

## release 签名现状

`app/build.gradle.kts` 已接通签名配置：从 `local.properties` 或 `-P` 参数读密钥，
**没有密钥时不报错**，产出 `app-release-unsigned.apk` 并在日志里用英文提示一行。

实测（用一个临时密钥库，验证完即删除，没有留在磁盘上）：
- `assembleRelease` 构建成功 → `app-release.apk` 22 MB
- `apksigner verify` → Verifies，APK Signature Scheme v2，RSA 2048，1 个签名者
- 包内 `.so` 全部是 `arm64-v8a`（无 x86_64 混入）
- 包内 `assets/chaquopy/requirements-common.imy` 解出 1072 个条目，含 `yt_dlp`（2026.8.19）→ Python 侧完整

**故意没开混淆**（`isMinifyEnabled = false`）：`proguard-rules.pro` 还是空的，而 Chaquopy 靠反射调
Python 桥。开着混淆又没写 keep 规则的结果是"装得上但一跑就崩"，而当前没有真机可验 release。
等 release 在真机跑通之后再开混淆并补规则。

## 已知功能缺陷（比"遗留小项"严重，优先修）

**安卓端「编码兜底」转码是死代码 —— 已真机确认（2026-09-13）。**

真机上直接跑打包进去的二进制：

```
$ adb shell run-as com.videodl.app <nativeLibraryDir>/libffmpeg.so -encoders
Encoders:
 ------
 VFS..D mjpeg
```

**只有一个 mjpeg 编码器**，没有 h264、没有 aac。`ytdlp_bridge.py` 请求的
`-c:v libx264` / `-c:a aac` 必然失败。

- 影响面：格式只提供 HEVC/AV1 时无法转成 H.264，相册/剪映可能打不开
  —— 正是这个功能本来要解决的场景
- 不受影响：合并音视频流走 `-c copy`，不需要编码器，日常下载正常（真机验证过）
- 根因不是漏接线，是许可证约束：libx264 是 GPL，能闭源商用的 ffmpeg 构建不含它
- **已改成快速失败**：转码前先探测编码器能力，没有 H.264 编码器就立刻如实说明并保留原文件，
  不再白跑两次 ffmpeg、也不再打出"参数不对"这种误导日志
- 修法：重建 `libffmpeg.so`，用 `--enable-libopenh264`（BSD）或
  `--enable-jni --enable-mediacodec --enable-encoder=h264_mediacodec`（Apache-2.0）+ 原生 aac
- 旧的文档说法（"`libffmpeg.so` 含 libx264"）**是错的**，已在 README 和交接文档改正

## 真机验证记录（2026-09-13，PJC110 / Android 15）

这一轮修完都上了真机验证，不是只看代码：

| 修的什么 | 真机证据 |
|---|---|
| 音频产物 m4a（原 mp3 根本出不来） | `runDownload: format=m4a quality=audio` → `download result: {"ok": true}`；产物 `Music/VideoDL/xxx.m4a`；MediaStore 归到 audio 集合；记录 `"仅音频 · m4a"` + `audio:true` |
| 取消被当成失败 | 记录 `status:"cancelled"`（旧版会写 `error`），界面显示「已取消」，不再弹「下载失败」通知 |
| 界面队列被 `begin()` 抹掉 | `dispatch next from queue, remaining=3` 之后界面仍然显示「队列（3）」 |
| 清理中间产物会误删用户文件 | logcat: `cleaned partial: 现在的小孩vs以前的小孩.f30080.mp4.part` —— 只删本次的分片 |
| **LazyColumn 重复 key 崩溃**（本轮新发现） | 同一个链接连排 4 条 → 旧版 `IllegalArgumentException: Key "q-<url>" was already used` 直接崩进程；改成按 job id 后不再崩，进程存活 |
| ffmpeg 没有 H.264 编码器 | `-encoders` 只列出 mjpeg（见上） |

测试期间产生的文件已清理（用 MediaStore 删除，避免留下僵尸条目），
只保留一个 528 KB 的 `.m4a` 作为"音频这条路真的通了"的证据。

## 遗留小项（carry to final review）

- T1: `app/build.gradle.kts` 里空的 `productFlavors { create("main") }` 是死配置 —— 要么删，要么写清用途
- T1: `ndk { abiFilters += listOf("arm64-v8a") }` 放在 `defaultConfig`，debug 也受约束 —— 现在是有意的，将来要跑模拟器得放开
- ~~T2: `AppConfig` 的字段映射在 `configFlow` 和 update lambda 里重复了一遍~~ —— 已解决：
  现在读、写两侧共用 `ConfigRepositoryImpl.toConfig()`（写侧仍逐个 put，但映射只有一份）
- T2: `ConfigRepositoryTest` 没有 `@Before DataStore.clear()` —— 有 flake 风险
- T6: `Duration` 用 `Int` 存，丢失亚秒精度 —— 下游格式化时注意
- T6: `cancel()` 没有和协程 scope 绑定，结构上偏松散
- T9: 几个 cosmetic 小项（http 大小写、null/empty 判断）
- 本轮新修但值得注意的约定：`Naming.isPartialOf()` 要求传**带扩展名的完整文件名**，
  传裸标题会什么都不匹配（刻意的保守行为，别"优化"成按标题前缀匹配 —— 那会删用户文件）

## 环境限制（一直存在，别再当新问题查）

- 无真机/无 AVD 时，instrumented test 只能编译、不能运行；system-images 未安装
- Chaquopy 的宿主 Python 版本随机器漂移，≥3.13 会撞 `cgi` 崩溃；实际嵌入的是 3.10
- 构建期 `pip install yt-dlp` 依赖网络
- Gradle 需要写 `~/.gradle`（工作区外）—— 沙箱限制下需要放开文件权限，否则报
  `FileNotFoundException: ...gradle-8.7-bin.zip.lck (拒绝访问)`

## Review 工具备注

Review 包偶尔会把整份 diff 重复一遍（controller 的 cosmetic 产物），不是代码缺陷，忽略即可。
