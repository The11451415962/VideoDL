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

## 遗留小项（carry to final review）

- T1: `app/build.gradle.kts` 里空的 `productFlavors { create("main") }` 是死配置 —— 要么删，要么写清用途
- T1: `ndk { abiFilters += listOf("arm64-v8a") }` 放在 `defaultConfig`，debug 也受约束 —— 现在是有意的，将来要跑模拟器得放开
- T2: `AppConfig` 的字段映射在 `configFlow` 和 update lambda 里重复了一遍 —— 抽个私有函数
- T2: `ConfigRepositoryTest` 没有 `@Before DataStore.clear()` —— 有 flake 风险
- T6: `Duration` 用 `Int` 存，丢失亚秒精度 —— 下游格式化时注意
- T6: `cancel()` 没有和协程 scope 绑定，结构上偏松散
- T9: 几个 cosmetic 小项（http 大小写、null/empty 判断）

## 环境限制（一直存在，别再当新问题查）

- 无真机/无 AVD 时，instrumented test 只能编译、不能运行；system-images 未安装
- Chaquopy 的宿主 Python 版本随机器漂移，≥3.13 会撞 `cgi` 崩溃；实际嵌入的是 3.10
- 构建期 `pip install yt-dlp` 依赖网络
- Gradle 需要写 `~/.gradle`（工作区外）—— 沙箱限制下需要放开文件权限，否则报
  `FileNotFoundException: ...gradle-8.7-bin.zip.lck (拒绝访问)`

## Review 工具备注

Review 包偶尔会把整份 diff 重复一遍（controller 的 cosmetic 产物），不是代码缺陷，忽略即可。
