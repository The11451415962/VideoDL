package com.videodl.app.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.net.Uri
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import androidx.core.content.FileProvider
import com.videodl.app.MainActivity
import com.videodl.app.MainApplication
import com.videodl.app.R
import com.videodl.app.data.ConfigRepositoryImpl
import com.videodl.app.data.DownloadCenter
import com.videodl.app.data.DownloadHistory
import com.videodl.app.data.DownloadRecord
import com.videodl.app.data.DownloadStatus
import com.videodl.app.data.FileRepository
import com.videodl.app.data.MediaTarget
import com.videodl.app.data.Naming
import com.videodl.app.data.QueuedItem
import com.videodl.app.data.VideoInfo
import com.videodl.app.engine.DownloadEvent
import com.videodl.app.engine.DownloadOptions
import com.videodl.app.engine.FormatOption
import com.videodl.app.engine.Platform
import java.io.File
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import android.util.Log

/**
 * 通知栏进度文字。抽成纯函数是为了能单测（队列数量要显示出来，
 * 用户切走 App 后靠它判断"后面还有几个"）。
 */
internal fun progressText(percent: Float, speed: String, eta: String, queued: Int = 0): String =
    buildString {
        append("${percent.toInt()}%")
        if (speed.isNotBlank()) append("  ·  ↓$speed")
        if (eta.isNotBlank()) append("  ·  剩余 $eta")
        if (queued > 0) append("  ·  队列 $queued")
    }

/** 时长文字（卡片左下显示用），例如 "4:12"；未知返回空串 */
internal fun formatDurationText(seconds: Int): String {
    if (seconds <= 0) return ""
    val h = seconds / 3600
    val m = (seconds % 3600) / 60
    val s = seconds % 60
    return if (h > 0) "$h:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}"
    else "$m:${s.toString().padStart(2, '0')}"
}

/**
 * 下载跑在前台 Service 里 —— 这是手机端必须的做法：
 * 用户切走 App、锁屏，下载都继续，通知栏实时显示进度和速度。
 *
 * 状态通过进程内的 [DownloadCenter] 暴露给界面，不需要 Binder/AIDL。
 */
class DownloadService : Service() {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private var lastNotify = 0L

    /** 当前正在跑的任务 + 排队等待的任务（一次只跑一个，但不丢请求） */
    private data class PendingJob(
        /** 唯一 id：界面靠它区分"同一个链接排了两次" */
        val id: Long,
        val url: String,
        val format: String,
        val quality: String,
        val proxyMode: String,
        val selector: String,
    )

    /** 任务 id 自增源（进程内唯一即可，不需要持久化） */
    private var nextJobId = 1L

    private var runningJob: Job? = null
    private val queue = ArrayDeque<PendingJob>()

    /** 当前这一次下载的展示信息，成功后写进下载记录 */
    private var currentTitle = ""
    private var currentThumb = ""
    private var currentFormatLabel = ""
    private var currentDuration = ""
    private var currentUploader = ""

    /** 当前任务的原始链接：抓信息就失败时用它当记录的标题，免得列表里出现空白卡片 */
    private var currentUrl = ""

    /** 当前任务是不是音频（记录里要存，界面筛选读它） */
    private var currentIsAudio = false

    /**
     * 下载记录 id 的自增后缀。
     * 只用毫秒时间戳的话，同一毫秒内写两条会撞 id，而下载列表的 LazyColumn 拿 id 当 key —
     * 撞了就直接崩。加个自增后缀把这种可能彻底去掉。
     */
    private var recordSeq = 0

    companion object {
        private const val TAG = "VideoDL"
        private const val CHANNEL_ID = "download"
        private const val NOTIF_ID = 1001
        /** 完成/失败的通知另用一个 id，免得被下一个任务的进度通知顶掉 */
        private const val NOTIF_ID_RESULT = 1002
        private const val MAX_QUEUE = 5

        const val ACTION_START = "com.videodl.app.START"
        const val ACTION_CANCEL = "com.videodl.app.CANCEL"
        const val ACTION_DROP_QUEUE = "com.videodl.app.DROP_QUEUE"
        const val EXTRA_URL = "url"
        const val EXTRA_FORMAT = "format"
        const val EXTRA_QUALITY = "quality"
        const val EXTRA_PROXY = "proxy"
        const val EXTRA_SELECTOR = "selector"
        const val EXTRA_JOB_ID = "job_id"

        fun start(
            ctx: Context,
            url: String,
            format: String = "",
            quality: String = "",
            proxyMode: String = "",
            selector: String = "",
        ) {
            val intent = Intent(ctx, DownloadService::class.java).apply {
                action = ACTION_START
                putExtra(EXTRA_URL, url)
                putExtra(EXTRA_FORMAT, format)
                putExtra(EXTRA_QUALITY, quality)
                putExtra(EXTRA_PROXY, proxyMode)
                putExtra(EXTRA_SELECTOR, selector)
            }
            ContextCompat.startForegroundService(ctx, intent)
        }

        /** 通知栏"取消"按钮。服务此时一定在运行，所以 startService 是安全的。 */
        fun cancel(ctx: Context) {
            runCatching {
                ctx.startService(Intent(ctx, DownloadService::class.java).apply {
                    action = ACTION_CANCEL
                })
            }.onFailure { Log.w(TAG, "cancel via service failed: ${it.message}") }
        }

        /** 只把某一项从队列里去掉（当前正在下的不动）；按 id 定位，因为链接可能重复 */
        fun dropQueued(ctx: Context, jobId: Long) {
            runCatching {
                ctx.startService(Intent(ctx, DownloadService::class.java).apply {
                    action = ACTION_DROP_QUEUE
                    putExtra(EXTRA_JOB_ID, jobId)
                })
            }.onFailure { Log.w(TAG, "drop queued failed: ${it.message}") }
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> {
                val url = intent.getStringExtra(EXTRA_URL).orEmpty()
                if (url.isBlank()) {
                    stopSelf()
                    return START_NOT_STICKY
                }
                val pending = PendingJob(
                    id = nextJobId++,
                    url = url,
                    format = intent.getStringExtra(EXTRA_FORMAT).orEmpty(),
                    quality = intent.getStringExtra(EXTRA_QUALITY).orEmpty(),
                    proxyMode = intent.getStringExtra(EXTRA_PROXY).orEmpty(),
                    selector = intent.getStringExtra(EXTRA_SELECTOR).orEmpty(),
                )
                if (runningJob != null) {
                    // 已经有一个在下了：排队，而不是把前一个悄悄取消掉。
                    //
                    // 这里**不能**调 goForeground —— 那会把正在下载的那个任务的通知
                    // 打回"准备下载… 0%"，用户看到进度倒退会以为重下了。
                    // 服务此刻本来就是前台（有任务在跑），不需要也不该再 startForeground。
                    if (queue.size >= MAX_QUEUE) {
                        DownloadCenter.log("[提示] 队列已满（$MAX_QUEUE 个），本次未加入")
                        Log.d(TAG, "queue full, rejected: $url")
                    } else {
                        queue.addLast(pending)
                        DownloadCenter.log("[提示] 已加入队列：排在 ${queue.size} 个之后")
                        Log.d(TAG, "queued (position=${queue.size}): $url")
                        publishQueue()
                    }
                } else {
                    startJobNow(pending)
                }
            }
            ACTION_DROP_QUEUE -> {
                // 从队列里单独去掉一项（队列卡片上的"移除"按钮）。
                // 按 id 而不是 url 移除：同一个链接可以排两次，按 url 会把两条一起删掉。
                val id = intent.getLongExtra(EXTRA_JOB_ID, -1L)
                val removed = queue.removeAll { it.id == id }
                if (removed) {
                    DownloadCenter.log("[提示] 已从队列中移除一项")
                    publishQueue()
                }
            }
            ACTION_CANCEL -> {
                // "停止"是用户意图明确的操作：取消当前这个，并清掉队列里等着的一起停
                (application as MainApplication).engine.cancel()
                if (queue.isNotEmpty()) {
                    DownloadCenter.log("[提示] 已清空队列（${queue.size} 个）")
                    queue.clear()
                    publishQueue()
                }
                DownloadCenter.log("[提示] 已请求取消当前下载")
            }
            else -> if (runningJob == null && queue.isEmpty()) stopSelf()
        }
        return START_NOT_STICKY
    }

    /** 把队列内容同步给界面（下载页要显示"队列（N）"） */
    private fun publishQueue() {
        val snapshot = queue.map {
            QueuedItem(id = it.id, url = it.url, label = it.quality.ifBlank { "默认画质" })
        }
        DownloadCenter.update { it.copy(queued = snapshot) }
    }

    /**
     * 真正开始一个任务：先把前台通知挂上（带「停止」按钮），再起协程。
     *
     * by startForegroundService 启动的服务必须尽快 startForeground，所以这一步
     * 放在这里是必须的；但只有"真的要开始下"时才调 —— 仅仅排队的请求不能调（见 onStartCommand）。
     */
    private fun startJobNow(pending: PendingJob) {
        goForeground(getString(R.string.notif_downloading_title), "准备下载…", 0, true)
        startJob(pending)
    }

    private fun startJob(pending: PendingJob) {
        runningJob = scope.launch {
            try {
                runDownload(
                    pending.url, pending.format, pending.quality,
                    pending.proxyMode, pending.selector,
                )
            } catch (e: Exception) {
                Log.e(TAG, "job failed", e)
                finishWithError(e.message ?: "未知错误")
            } finally {
                runningJob = null
                dispatchNext()
            }
        }
    }

    /** 当前任务结束后：还有排队就接着下，没有就收工（关掉前台通知） */
    private fun dispatchNext() {
        val next = queue.removeFirstOrNull()
        publishQueue()
        if (next != null) {
            DownloadCenter.log("[提示] 开始队列中的下一个（还剩 ${queue.size} 个）")
            Log.d(TAG, "dispatch next from queue, remaining=${queue.size}")
            startJobNow(next)
        } else {
            Log.d(TAG, "queue empty, stopping service")
            stopForegroundCompat(true)
            stopSelf()
        }
    }

    override fun onDestroy() {
        scope.cancel()
        super.onDestroy()
    }

    // ---------------------------------------------------------------- 下载主流程

    private suspend fun runDownload(
        url: String,
        formatArg: String,
        qualityArg: String,
        proxyArg: String,
        selectorArg: String,
    ) {
        val engine = (application as MainApplication).engine
        val config = ConfigRepositoryImpl(this).configFlow.first()
        // 参数留空表示"按用户配置来"（分享直达就是这种情况）
        val format = formatArg.ifBlank { config.defaultFormat }
        val quality = qualityArg.ifBlank { config.defaultQuality }
        val proxyMode = proxyArg.ifBlank { config.proxyMode }

        DownloadCenter.begin()
        DownloadCenter.log("[提示] 开始处理：$url")
        currentUrl = url
        // 关键参数写进 logcat：出问题时要能一眼看出"这次到底按什么格式下的"
        Log.d(TAG, "runDownload: format=$format quality=$quality " +
            "selector=${selectorArg.ifBlank { "-" }} proxy=$proxyMode")

        // 开相册时先下到 App 自己的目录，发布成功后删除；关相册则直接存用户选的目录
        val landingDir = if (config.exportToGallery) {
            FileRepository.defaultBaseDir(this)
        } else {
            FileRepository.resolveBaseDir(this, config)
        }

        val options = DownloadOptions(
            url = url,
            outputPath = FileRepository.buildOutputPath(landingDir, "video", format, quality),
            proxyMode = proxyMode,
            proxyUrl = config.proxyUrl,
            cookieMode = config.cookieMode,
            cookiePath = config.cookiePathUri,
            format = format,
            quality = quality,
            platform = Platform.detect(url),
            ffmpegLocation = FileRepository.ffmpegLocation(this),
            formatSelector = selectorArg,
        )

        // 1) 抓信息（为了拿到标题做文件名 / 提前展示）
        val info = runCatching {
            withContext(Dispatchers.IO) { engine.fetchInfo(url, options) }
        }.onFailure { Log.w(TAG, "fetchInfo failed: ${it.message}") }.getOrNull()

        DownloadCenter.update {
            it.copy(
                status = DownloadStatus.Downloading,
                info = info?.let { i -> VideoInfo(i.title, i.uploader, i.duration, i.resolution, i.thumbnail) },
            )
        }
        currentTitle = info?.title.orEmpty()
        currentThumb = info?.thumbnail.orEmpty()
        currentUploader = info?.uploader.orEmpty()
        currentDuration = formatDurationText(info?.duration ?: 0)
        // 展示用的标签要干净：不要把 yt-dlp 的术语/选择器原文漏到界面上
        val qualityLabel = when (quality.ifBlank { "best" }) {
            "best" -> "最佳"
            "audio" -> "仅音频"
            else -> quality
        }
        currentFormatLabel = listOf(qualityLabel, format)
            .filter { it.isNotBlank() }
            .joinToString(" · ")
        // 提前算好：失败/取消的记录也要带上"音频/视频"，否则界面筛选会分错
        currentIsAudio = MediaTarget.isAudio(format, quality)

        val finalOptions = info?.title?.takeIf { it.isNotBlank() }?.let { title ->
            options.copy(
                outputPath = FileRepository.buildOutputPath(landingDir, title, format, quality),
            )
        } ?: options

        // 2) 下载
        var producedPath: String? = null
        var errorMessage: String? = null
        var wasCancelled = false
        engine.download(finalOptions).collect { ev ->
            when (ev) {
                is DownloadEvent.Progress -> {
                    DownloadCenter.update {
                        it.copy(percent = ev.percent, speed = ev.speed, eta = ev.eta)
                    }
                    notifyProgress(ev.percent, ev.speed, ev.eta)
                }
                is DownloadEvent.Log -> DownloadCenter.log(ev.line)
                is DownloadEvent.Finished -> producedPath = ev.filePath
                is DownloadEvent.Error -> errorMessage = ev.message
                DownloadEvent.Cancelled -> wasCancelled = true
                else -> {}
            }
        }

        // 用户自己按的「停止」不是失败：单独收尾，别报错也别写 error 记录
        if (wasCancelled) {
            cleanupPartials(File(landingDir), File(finalOptions.outputPath).name)
            finishCancelled()
            return
        }

        errorMessage?.let {
            cleanupPartials(File(landingDir), File(finalOptions.outputPath).name)
            finishWithError(it)
            return
        }

        val file = File(producedPath ?: finalOptions.outputPath)
        if (!file.isFile) {
            cleanupPartials(File(landingDir), File(finalOptions.outputPath).name, file.name)
            finishWithError("下载结束但找不到输出文件")
            return
        }

        // 3) 发布到相册（剪映、相册等 App 直接可见；不需要任何存储权限）
        val sizeText = FormatOption.formatBytes(file.length())
        if (!config.exportToGallery) {
            DownloadCenter.update { it.copy(destination = file.parent.orEmpty()) }
            saveRecord(file.absolutePath, sizeText, "done")
            finishOk(file.absolutePath, file.name)
            return
        }

        val isAudio = currentIsAudio
        val mime = MediaTarget.mime(format, quality)
        val uri = withContext(Dispatchers.IO) {
            FileRepository.publishToGallery(this@DownloadService, file, mime, isAudio)
        }
        if (uri != null) {
            DownloadCenter.note(
                "[完成] 已存入相册：${if (isAudio) "Music" else "Movies"}/${FileRepository.GALLERY_SUBDIR}/${file.name}"
            )
            DownloadCenter.update { it.copy(destination = "系统相册") }
            withContext(Dispatchers.IO) { runCatching { file.delete() } }
            saveRecord(uri.toString(), sizeText, "done")
            finishOk(uri.toString(), file.name)
        } else {
            DownloadCenter.note("[警告] 存入相册失败，文件保留在：${file.absolutePath}")
            DownloadCenter.update { it.copy(destination = file.parent.orEmpty()) }
            saveRecord(file.absolutePath, sizeText, "done")
            finishOk(file.absolutePath, file.name)
        }
    }

    /** 写一条下载记录（下载列表标签页读它） */
    private fun saveRecord(uri: String, sizeText: String, status: String) {
        runCatching {
            DownloadHistory.add(
                this,
                DownloadRecord(
                    id = "${System.currentTimeMillis()}-${recordSeq++}",
                    // 抓信息就失败时 currentTitle 是空的，退回链接 —— 否则列表里会出现
                    // 一张没标题、也没播放键的空白卡片
                    title = currentTitle.ifBlank { currentUrl.ifBlank { File(uri).name } },
                    uri = uri,
                    thumb = currentThumb,
                    formatLabel = currentFormatLabel,
                    sizeText = sizeText,
                    status = status,
                    timeMs = System.currentTimeMillis(),
                    durationText = currentDuration,
                    uploader = currentUploader,
                    isAudio = currentIsAudio,
                ),
            )
        }.onFailure { Log.w(TAG, "save record failed: ${it.message}") }
    }

    private fun finishOk(target: String, displayName: String) {
        DownloadCenter.update {
            it.copy(
                status = DownloadStatus.Done,
                percent = 100f,
                speed = "",
                eta = "",
                finishedUri = target,
                finishedDisplayName = displayName,
            )
        }
        val openIntent = buildOpenIntent(target)
        val pi = PendingIntent.getActivity(
            this, 2, openIntent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        val notif = NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(getString(R.string.notif_complete_title))
            .setContentText(displayName)
            .setSmallIcon(android.R.drawable.stat_sys_download_done)
            .setContentIntent(pi)
            .setAutoCancel(true)
            .setOngoing(false)
            .build()
        // 用独立 id：队列里下一个任务的进度通知不会把它顶掉
        safeNotify(notif, NOTIF_ID_RESULT)
        // 不在这里停服务：还有排队任务就接着下（见 dispatchNext）
    }

    /**
     * 清掉这次下载留下的中间产物（`.part` / `.f30080.mp4` / `.compat.mp4` …）。
     *
     * 只按**本次的完整文件名（含扩展名）**做前缀匹配。
     *
     * 旧版按"标题"匹配，标题是用户可见的短词，而落地目录可能是用户自己选的保存目录 ——
     * 一次失败的"猫"会把该目录下所有以"猫"开头的文件删掉，包括早就下好的"猫和老鼠.mp4"。
     * 带上扩展名后 "猫.mp4" 命中不了 "猫和老鼠.mp4"，但仍然命中
     * "猫.mp4.part" / "猫.mp4.f137.mp4" / "猫.mp4.compat.mp4" 这些真正的中间产物。
     */
    private fun cleanupPartials(dir: File, vararg outputFileNames: String) {
        if (!dir.isDirectory) return
        val prefixes = outputFileNames.filter { it.isNotBlank() }
        if (prefixes.isEmpty()) return
        runCatching {
            dir.listFiles()?.forEach { f ->
                if (f.isFile && Naming.isPartialOf(f.name, prefixes)) {
                    if (f.delete()) Log.d(TAG, "cleaned partial: ${f.name}")
                }
            }
        }
    }

    /**
     * 用户主动取消的收尾 —— 和失败分开。
     *
     * 旧版把取消也走 finishWithError，结果用户点了「停止」却收到「下载失败」通知，
     * 下载列表里还多一条 status="error" 的记录（而 DownloadRecord 里明明定义了
     * "cancelled" 这个状态，只是从来没人写过）。
     */
    private fun finishCancelled() {
        DownloadCenter.update {
            it.copy(status = DownloadStatus.Cancelled, percent = 0f, speed = "", eta = "")
        }
        DownloadCenter.log("[提示] 已取消当前下载")
        saveRecord("", "", "cancelled")
        val pi = PendingIntent.getActivity(
            this, 3,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        val notif = NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(getString(R.string.notif_cancelled_title))
            .setContentText(currentTitle.ifBlank { getString(R.string.notif_cancelled_text) })
            .setSmallIcon(android.R.drawable.stat_sys_download_done)
            .setContentIntent(pi)
            .setAutoCancel(true)
            .setOngoing(false)
            .build()
        safeNotify(notif, NOTIF_ID_RESULT)
    }

    private fun finishWithError(message: String) {
        DownloadCenter.update { it.copy(status = DownloadStatus.Error, error = message, eta = "") }
        DownloadCenter.log("[失败] $message")
        // 失败也记一条，用户能在下载列表里看到并重试
        saveRecord("", "", "error")
        val pi = PendingIntent.getActivity(
            this, 3,
            Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        val notif = NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(getString(R.string.notif_error_title))
            .setContentText(message)
            .setSmallIcon(android.R.drawable.stat_notify_error)
            .setContentIntent(pi)
            .setAutoCancel(true)
            .setOngoing(false)
            .build()
        safeNotify(notif, NOTIF_ID_RESULT)
        // 同样不在这里停服务：队列里还有就继续
    }

    /** 完成后点通知即可播放：相册文件用 content://，未开相册时用 FileProvider 共享 */
    private fun buildOpenIntent(target: String): Intent {
        val uri: Uri = if (target.startsWith("content://")) {
            Uri.parse(target)
        } else {
            runCatching {
                FileProvider.getUriForFile(this, "$packageName.fileprovider", File(target))
            }.getOrNull() ?: Uri.fromFile(File(target))
        }
        val mime = when {
            target.endsWith(".m4a", true) || target.endsWith(".mp3", true) -> MediaTarget.AUDIO_MIME
            target.endsWith(".webm", true) -> "video/webm"
            else -> "video/*"
        }
        return Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, mime)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
    }

    // ---------------------------------------------------------------- 通知

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val ch = NotificationChannel(
                CHANNEL_ID,
                getString(R.string.notif_channel_name),
                NotificationManager.IMPORTANCE_LOW,
            ).apply { setShowBadge(false) }
            (getSystemService(NOTIFICATION_SERVICE) as NotificationManager)
                .createNotificationChannel(ch)
        }
    }

    private fun goForeground(title: String, text: String, percent: Int, withCancel: Boolean) {
        val notif = buildProgressNotification(title, text, percent, withCancel)
        ServiceCompat.startForeground(
            this, NOTIF_ID, notif,
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC
            } else {
                0
            },
        )
    }

    private fun buildProgressNotification(
        title: String,
        text: String,
        percent: Int,
        withCancel: Boolean,
    ): Notification {
        val contentPi = PendingIntent.getActivity(
            this, 1,
            Intent(this, MainActivity::class.java).apply {
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            },
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        val builder = NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(title)
            .setContentText(text)
            .setSmallIcon(android.R.drawable.stat_sys_download)
            .setContentIntent(contentPi)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setProgress(100, percent.coerceIn(0, 100), percent <= 0)
        if (withCancel) {
            val cancelPi = PendingIntent.getService(
                this, 4,
                Intent(this, DownloadService::class.java).apply { action = ACTION_CANCEL },
                PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
            )
            builder.addAction(
                android.R.drawable.ic_menu_close_clear_cancel,
                getString(R.string.btn_stop),
                cancelPi,
            )
        }
        return builder.build()
    }

    private fun notifyProgress(percent: Float, speed: String, eta: String) {
        val now = System.currentTimeMillis()
        if (now - lastNotify < 400 && percent < 100f) return
        lastNotify = now
        val text = progressText(percent, speed, eta, queue.size)
        safeNotify(buildProgressNotification(
            getString(R.string.notif_downloading_title), text, percent.toInt(), true,
        ))
    }

    private fun safeNotify(notif: Notification, id: Int = NOTIF_ID) {
        runCatching {
            NotificationManagerCompat.from(this).notify(id, notif)
        }.onFailure { Log.w(TAG, "notify failed: ${it.message}") }
    }

    private fun stopForegroundCompat(removeNotification: Boolean) {
        runCatching {
            ServiceCompat.stopForeground(
                this,
                if (removeNotification) ServiceCompat.STOP_FOREGROUND_REMOVE
                else ServiceCompat.STOP_FOREGROUND_DETACH,
            )
        }
    }
}
