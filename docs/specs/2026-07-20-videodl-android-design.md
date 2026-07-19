# VideoDL Android 设计文档

> 来源：桌面版 `shipinxiazaiqi` (Python + tkinter + yt-dlp) 的 Android 重制。
> 日期：2026-07-20。状态：已评审待实现。
> 许可证：MIT（与桌面版一致，Chaquopy 开源使用免费）。

## 0. 一句话目标

做一款**原生 Android 视频下载器**：保留桌面版 yt-dlp 的全部下载核心能力，并按手机交互重设计——**系统分享直达、通知栏进度、前台 Service 后台下载**是 v1 必须上线的手机差异化功能。不硬搬桌面版上手机无意义的功能（浏览器 Cookie 解密等）。

## 1. 核心设计决策（已确认）

| 决策 | 结论 | 理由 |
|---|---|---|
| 技术栈 | Kotlin + Jetpack Compose + Chaquopy | 原生、现代、Chaquopy 可直接在进程内跑 yt-dlp |
| yt-dlp 调用方式 | **嵌入调用**（Chaquopy），不搞子进程 | 进度靠 `progress_hook` 回调拿结构化数据，取消删干净，不靠正则扫 stdout |
| 下载引擎定位 | 桌面版逻辑 1:1 搬运，不重写 | `resolve_format_string` / `resolve_proxy` / Cookie / 平台识别直接翻译到 Kotlin；"浏览器 Cookie 解密"整个删掉（Android 无 DPAPI） |
| 保存路径策略 | SAF URI，不存裸路径字符串 | Android 10+ Scoped Storage 强制要求 |
| 视觉风格 | Material 3 + 跟系统色，深色模式自动 | 现代、省事、留品牌色接口 |
| 架构 | 单 Activity + Compose 多页 + MVVM + StateFlow 单向数据流 | Google 推荐现代架构 |
| minSdk / ABI | minSdk 26 (Android 8.0) / 仅 arm64-v8a | 覆盖 98%+ 设备，控制 APK 60–90 MB |
| 发布 | 开源 MIT，首选 F-Droid / GitHub Releases | 贴合开源定位 |

## 2. 系统架构

### 2.1 分层

```
┌─────────────────────────────────────────────┐
│  UI 层 (Jetpack Compose + Material 3)        │
│    MainActivity ┬─ HomeScreen               │
│                 ├─ SettingsScreen           │
│                 └─ 对话框（SAF 选路径等）    │
├─────────────────────────────────────────────┤
│  ViewModel 层                                │
│    HomeViewModel  ── 状态、按钮动作、进度     │
│    SettingsViewModel                         │
├─────────────────────────────────────────────┤
│  Engine 层 (Chaquopy 嵌入 CPython)           │
│    YtdlpEngine ── 启动 Python、调用 yt-dlp    │
│    ProgressParser ── 回调 → Kotlin Flow       │
├─────────────────────────────────────────────┤
│  Data 层                                     │
│    ConfigRepository ── DataStore 持久化       │
│    FileRepository  ── SAF 文件、命名去重       │
└─────────────────────────────────────────────┘
```

### 2.2 桌面版 → Android 映射

| 桌面 (`video_downloader.py`) | Android 落点 |
|---|---|
| `Downloader` 类 + 线程 | `YtdlpEngine` + `HomeViewModel` + Kotlin 协程 |
| `SettingsDialog` | `SettingsScreen` (Compose 全屏页) |
| `config.json` + `save_config()` | `ConfigRepository` + DataStore |
| `get_next_filepath` 命名 + 日期文件夹 | `FileRepository`（日期文件夹 v1 删） |
| `os.startfile` 打开文件夹 | `ACTION_VIEW` 打开视频文件 |
| `_paste_from_clipboard` 一键粘贴 | 系统分享 Intent（等价物） + 剪贴板提取保留 |
| 桌面版无 | 通知栏进度（前台 Service） |

### 2.3 包结构（单 Gradle Module，按层分包）

```
com.videodl.app/
├── ui/                  # Compose 屏幕 + 主题
│   ├── home/            # HomeScreen + HomeViewModel
│   ├── settings/        # SettingsScreen + SettingsViewModel
│   └── theme/           # Material 3 主题
├── engine/              # yt-dlp 引擎
│   ├── YtdlpEngine.kt
│   ├── DownloadOptions.kt
│   └── PythonFiles.kt   # 自定义 .py 放这里
├── data/                # 持久化
│   ├── ConfigRepository.kt
│   └── FileRepository.kt
├── service/             # 前台 Service + 通知
│   └── DownloadService.kt
└── ShareReceiver.kt     # 系统分享直达入口
```

## 3. 引擎层详细设计（Chaquopy + yt-dlp）

### 3.1 关键工程要点

| 问题 | 解法 |
|---|---|
| CPython 嵌入 APK | Chaquopy Gradle 插件自动把标准库打进 APK（≈ 8–12 MB） |
| yt-dlp 源码打入 | `requirements { pip { install("yt-dlp") } }`，Gradle 构建时抓最新版 |
| yt-dlp 升级 | 启动时后台静默检查 → 有新版本弹提示（-v1 不做 UI 内 -U 按钮） |
| ffmpeg | 单独交叉编译 aarch64 的 ffmpeg .so，作原生库打入 APK，通过 `--ffmpeg-location` 传给 yt-dlp |
| 线程安全 | 单一线程 + 协程 跑所有 yt-dlp 调用，用 Channel 把事件传回 UI |
| 取消下载 | 抛 Python 异常 / 停止回调，不搞"杀进程留僵尸" |
| release 体积 | 仅 arm64-v8a，预估 60–90 MB |

### 3.2 引擎对外接口

```kotlin
sealed class DownloadEvent {
    object Started : DownloadEvent()
    data class Info(val title: String, val uploader: String,
                    val duration: Int, val resolution: String) : DownloadEvent()
    data class Progress(val percent: Float, val speed: String, val eta: String) : DownloadEvent()
    data class Finished(val filePath: String) : DownloadEvent()
    data class Error(val message: String) : DownloadEvent()
}

interface YtdlpEngine {
    fun fetchInfo(url: String): DownloadEvent.Info
    fun download(url: String, options: DownloadOptions): Flow<DownloadEvent>
    fun cancel()
    fun upgradeYtdlp(): Flow<String>
}
```

UI 层只跟这个接口和事件流打交道，不知道底下是 Python。换引擎（几乎不可能）UI 不用改。

### 3.3 从桌面版搬运清单

**直接 1:1 翻译到 Kotlin：**
- `resolve_format_string(fmt, quality, platform)` —— 平台相关的 format 选择逻辑（YouTube 用 ext filter，Bilibili 不限 ext）
- `resolve_proxy(config, url)` —— auto/direct/proxy 代理决策
- `detect_platform(url)` —— URL → 平台名
- B站加 `Referer` / `Origin` 头（防 HTTP 412）
- Cookie 从文件读（`--cookies`）
- 剪贴板智能提取 URL（容错抖音分享文本）
- 重名自动序号命名 `get_next_filepath`

**整个删掉（手机做不到 / 无意义）：**
- `export_cookies.py` —— Chrome DPAPI 解密（Windows 专属）
- `cookie_mode = "browser"` / `cookie_browser` 选项
- ffmpeg"用户指定路径"手动选（改为 App 自管理 .so）
- 日期子文件夹（v1 不做，v2 看需求）
- `os.startfile` 打开文件夹

## 4. UI 与交互设计

### 4.1 屏幕清单

| 屏幕 | 说明 |
|---|---|
| **HomeScreen** | 链接输入 + 视频信息卡片 + 格式/画质/代理选择 + 进度条 + 按钮 + 可折叠日志 |
| **SettingsScreen** | 保存路径、代理、Cookie、格式/画质默认值、自动打开文件 |
| SAF 对话框 | 系统文件选择器选保存路径 / Cookie 文件 |

### 4.2 HomeScreen 布局

```
┌─────────────────────────────┐
│  📋 链接输入栏  [粘贴]        │  ← 点输入栏自动读剪贴板
├─────────────────────────────┤
│  视频信息卡片                  │  ← 抓信息后展示
│  标题：xxx                    │
│  上传者：xxx  时长 3:21        │
├─────────────────────────────┤
│  格式 [MP4▾]  画质 [最佳▾]     │
│  代理 [自动▾]                  │
├─────────────────────────────┤
│  ━━━━━━━━━━━━━━━━ 47.2%      │  ← 进度条 + 百分比
│  1.3 MB/s  剩余 0:12          │
├─────────────────────────────┤
│  [🚀 开始下载] [⏹ 停止]        │
├─────────────────────────────┤
│  ▸ 下载日志（可折叠）           │
└─────────────────────────────┘
```

### 4.3 手机端特有交互

1. **系统分享直达（v1 必须）** —— 注册 `ACTION_SEND` + `text/plain` 的 `<intent-filter>`；抖音/浏览器点「分享 → 本 App」直接进主页并自动填链接。这是手机端核心入口，桌面版"一键粘贴"的等价物。
2. **通知栏进度（v1 必须）** —— 前台 Service 拉一条常驻通知：进度条 + 速度 + 取消按钮。用户可离开 App 下载不停；点通知回 App；完成变"下载完成"+ 点击打开文件。
3. **完成直接打开文件** —— `ACTION_VIEW` + 正确 mime type 打开视频，而不是桌面版那种打开文件夹。
4. **剪贴板智能提取保留** —— 桌面版容错抖音分享文本的逻辑原样搬到手机。

### 4.4 状态管理

单向数据流：Compose 状态全在 `HomeViewModel` 里用 `StateFlow` 管，UI 只做两件事——把事件（按钮点击、分享 Intent）转发给 ViewModel，把 StateFlow 渲染成界面。

```kotlin
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

enum class DownloadStatus { Idle, Fetching, Downloading, Done, Error }
```

## 5. 配置与持久化

### 5.1 DataStore 配置项

```kotlin
data class AppConfig(
    val saveDirUri: String = "",         // SAF 树 URI
    val proxyMode: String = "auto",
    val proxyUrl: String = "http://127.0.0.1:7897",
    val cookieMode: String = "none",     // none | file（无 browser）
    val cookiePathUri: String = "",
    val defaultFormat: String = "mp4",
    val defaultQuality: String = "best",
    val autoOpenFile: Boolean = true,
)
```

用 Jetpack DataStore (Preferences)：轻量、协程原生、类型安全、异步读写不卡 UI。

### 5.2 SAF 路径

保存路径 / Cookie 路径存 SAF URI 不存裸路径。选一次文件夹 → 持久化 URI 权限 → 之后顺着它写文件（Android 10+ 强制规范，唯一合规写法）。

## 6. 依赖清单

| 类别 | 库 | 用途 |
|---|---|---|
| UI | Jetpack Compose + Material 3 | 界面 |
| 架构 | lifecycle-viewmodel-compose + StateFlow | 状态管理 |
| 持久化 | androidx.datastore:datastore-preferences | 配置 |
| 异步 | Kotlin Coroutines | 引擎回调 → UI |
| 引擎 | Chaquopy | 嵌入 CPython |
| 构建 | Android Gradle Plugin, Kotlin Gradle Plugin | 编译 |

零第三方 UI 控件库——纯官方栈，减依赖维护风险、减体积。

## 7. v1 功能范围边界（防需求滑坡）

### 7.1 v1 必须有

- 粘贴/分享链接 → 抓视频信息 → 选格式/画质/代理 → 下载 (yt-dlp) → 进度 → 完成打开文件
- 通知栏进度（前台 Service）
- 系统分享直达
- 设置页（保存路径、代理、Cookie、格式/画质默认值、自动打开文件）
- 取消下载

### 7.2 v1 明确不做

- 下载队列 / 多任务
- 浏览器 Cookie 导入（Android 无 DPAPI）
- 日期子文件夹
- yt-dlp UI 内一键升级（后台静默检查）
- 账号登录、内嵌播放器、社交功能
- 下载历史记录

### 7.3 以后 v2 再看

- 下载历史记录（Room 数据库）
- 批量排队、定时下载
- 主题自定义

## 8. 构建与发布

- minSdk 26 (Android 8.0)，release 仅 arm64-v8a
- 首次用 debug 签名跑；正式发布再生成正式 keystore（一条命令）
- 渠道：F-Droid（开源首选）/ GitHub Releases APK 直装 / 应用商店
- 版本号语义化（SemVer），桌面版版号对齐

## 9. 风险与备案

| 风险 | 影响 | 备案 |
|---|---|---|
| Chaquopy 许可证 | 闭源商用需付费 | 默认 MIT 开源免费；走闭源需购授权 |
| yt-dlp 站点协议变更 | 部分站点下载失败 | yt-dlp 上游修复 → 我们更新 pip 包 |
| 大厂封杀 yt-dlp App | 应用商店下架 | 走 F-Droid + GitHub 直装，不被商店卡脖子 |
| ffmpeg aarch64 .so 构建失败 | 合并视频/音频流不可用 | 单独下载预编译的 aarch64 ffmpeg .so（见 Section 3.1 ffmpeg 行）或引入 mobile-ffmpeg 类库 |
| Scoped Storage 写入限制 | 部分机型写文件失败 | SAF + MediaStore 兜底 |
