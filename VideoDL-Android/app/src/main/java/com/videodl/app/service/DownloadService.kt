package com.videodl.app.service

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import com.videodl.app.MainApplication
import com.videodl.app.data.AppConfig
import com.videodl.app.data.ConfigRepositoryImpl
import com.videodl.app.data.FileRepository
import com.videodl.app.engine.DownloadEvent
import com.videodl.app.engine.DownloadOptions
import com.videodl.app.engine.Platform
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.runBlocking

class DownloadService : Service() {

    private val scope = CoroutineScope(Dispatchers.Main + Job())
    private var currentJob: Job? = null
    private val notificationId = 1001

    companion object {
        const val ACTION_START = "com.videodl.app.START"
        const val ACTION_CANCEL = "com.videodl.app.CANCEL"
        const val EXTRA_URL = "url"

        fun start(ctx: Context, url: String) {
            ctx.startForegroundService(Intent(ctx, DownloadService::class.java).apply {
                action = ACTION_START; putExtra(EXTRA_URL, url)
            })
        }
        fun cancel(ctx: Context) {
            ctx.startService(Intent(ctx, DownloadService::class.java).apply { action = ACTION_CANCEL })
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        createChannel()
        startForeground(notificationId, buildNotification("准备下载...", 0))
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> intent.getStringExtra(EXTRA_URL)?.let { startDownload(it) }
            ACTION_CANCEL -> { currentJob?.cancel(); stopSelf() }
        }
        return START_NOT_STICKY
    }

    private fun startDownload(url: String) {
        val engine = (application as MainApplication).engine
        val config = runBlocking { ConfigRepositoryImpl(this@DownloadService).configFlow.first() }
        val baseDir = FileRepository.resolveBaseDir(this, config)
        val outputPath = FileRepository.buildOutputPath(baseDir, "video", config.defaultFormat, config.defaultQuality)
        val options = DownloadOptions(
            url = url, outputPath = outputPath,
            proxyMode = config.proxyMode, proxyUrl = config.proxyUrl,
            cookieMode = config.cookieMode, cookiePath = config.cookiePathUri,
            format = config.defaultFormat, quality = config.defaultQuality,
            platform = Platform.detect(url),
            ffmpegLocation = FileRepository.ffmpegLocation(this),
        )
        currentJob = engine.download(options).onEach { ev ->
            when (ev) {
                is DownloadEvent.Progress -> updateNotification(
                    "${config.defaultFormat} ${config.defaultQuality}", ev.percent)
                is DownloadEvent.Finished -> showComplete(ev.filePath)
                is DownloadEvent.Error -> showError(ev.message)
                else -> {}
            }
        }.launchIn(scope)
    }

    private fun createChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val ch = NotificationChannel("download", "下载进度", NotificationManager.IMPORTANCE_LOW)
            (getSystemService(NOTIFICATION_SERVICE) as NotificationManager).createNotificationChannel(ch)
        }
    }

    private fun buildNotification(text: String, percent: Int) = NotificationCompat.Builder(this, "download")
        .setContentTitle("VideoDL 下载中").setContentText(text)
        .setSmallIcon(android.R.drawable.stat_sys_download).setOngoing(true)
        .setProgress(100, percent.coerceIn(0, 100), false).build()

    private fun updateNotification(text: String, percent: Float) {
        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(notificationId, buildNotification(text, percent.toInt()))
    }

    private fun showComplete(path: String) {
        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(notificationId, NotificationCompat.Builder(this, "download")
            .setContentTitle("下载完成").setContentText(path)
            .setSmallIcon(android.R.drawable.stat_sys_download_done).setAutoCancel(true).build())
        stopSelf()
    }

    private fun showError(msg: String) {
        val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
        nm.notify(notificationId, NotificationCompat.Builder(this, "download")
            .setContentTitle("下载失败").setContentText(msg)
            .setSmallIcon(android.R.drawable.stat_notify_error).setAutoCancel(true).build())
        stopSelf()
    }
}
