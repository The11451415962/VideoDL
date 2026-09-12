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
        val url: String,
        val format: String,
        val quality: String,
        val proxyMode: String,
        val selector: String,
    )

    private var runningJob: Job? = null
    private val queue = ArrayDeque<PendingJob>()

    /** 当前这一次下载的展示信息，成功后写进下载记录 */
    private var currentTitle = ""
    private var currentThumb = ""
    private var currentFormatLabel = ""

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

        /** 只把某一项从队列里去掉（当前正在下的不动） */
        fun dropQueued(ctx: Context, url: String) {
            runCatching {
                ctx.startService(Intent(ctx, DownloadService::class.java).apply {
                    action = ACTION_DROP_QUEUE
                    putExtra(EXTRA_URL, url)
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
                    url = url,
                    format = intent.getStringExtra(EXTRA_FORMAT).orEmpty(),
                    quality = intent.getStringExtra(EXTRA_QUALITY).orEmpty(),
                    proxyMode = intent.getStringExtra(EXTRA_PROXY).orEmpty(),
                    selector = intent.getStringExtra(EXTRA_SELECTOR).orEmpty(),
                )
                goForeground(getString(R.string.notif_downloading_title), "准备下载…", 0, false)
                if (runningJob != null) {
                    // 已经有一个在下了：排队，而不是把前一个悄悄取消掉
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
                    startJob(pending)
                }
            }
            ACTION_DROP_QUEUE -> {
                // 从队列里单独去掉一项（队列卡片上的"移除"按钮）
                val url = intent.getStringExtra(EXTRA_URL).orEmpty()
                val removed = queue.removeAll { it.url == url }
                if (removed) {
                    DownloadCenter.log("[提示] 已从队列中移除：$url")
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
        val snapshot = queue.map { QueuedItem(url = it.url, label = it.quality.ifBlank { "默认画质" }) }
        DownloadCenter.update { it.copy(queued = snapshot) }
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
            goForeground(getString(R.string.notif_downloading_title), "准备下载…", 0, false)
            startJob(next)
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
        // 展示用的标签要干净：不要把 yt-dlp 的选择器原文漏到界面上
        currentFormatLabel = listOf(quality.ifBlank { "best" }, format)
            .filter { it.isNotBlank() }
            .joinToString(" · ")

        val finalOptions = info?.title?.takeIf { it.isNotBlank() }?.let { title ->
            options.copy(
                outputPath = FileRepository.buildOutputPath(landingDir, title, format, quality),
            )
        } ?: options

        // 2) 下载
        var producedPath: String? = null
        var errorMessage: String? = null
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
                else -> {}
            }
        }

        errorMessage?.let {
            cleanupPartials(File(landingDir), File(finalOptions.outputPath).nameWithoutExtension)
            finishWithError(it)
            return
        }

        val file = File(producedPath ?: finalOptions.outputPath)
        if (!file.isFile) {
            cleanupPartials(File(landingDir), file.nameWithoutExtension)
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

        val isAudio = format == "mp3" || quality == "audio"
        val mime = when {
            isAudio -> "audio/mpeg"
            format == "webm" -> "video/webm"
            else -> "video/mp4"
        }
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
                    id = System.currentTimeMillis().toString(),
                    title = currentTitle.ifBlank { File(uri).name },
                    uri = uri,
                    thumb = currentThumb,
                    formatLabel = currentFormatLabel,
                    sizeText = sizeText,
                    status = status,
                    timeMs = System.currentTimeMillis(),
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
     * 清掉这次下载留下的中间产物（.part / .f30080.mp4 / .compat.mp4 …）。
     * 取消或失败时不清理的话，Android/data 里会攒一堆肉眼看不见的垃圾。
     */
    private fun cleanupPartials(dir: File, baseName: String) {
        if (!dir.isDirectory) return
        runCatching {
            dir.listFiles()?.forEach { f ->
                if (f.isFile && baseName.isNotBlank() &&
                    (f.name.startsWith(baseName) || f.name.endsWith(".part"))
                ) {
                    if (f.delete()) Log.d(TAG, "cleaned partial: ${f.name}")
                }
            }
        }
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
            target.endsWith(".mp3", true) -> "audio/mpeg"
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
