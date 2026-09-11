package com.videodl.app

import android.app.Application
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import com.videodl.app.engine.YtdlpEngine
import com.videodl.app.engine.YtdlpEngineImpl

class MainApplication : Application() {
    lateinit var engine: YtdlpEngine
        private set

    override fun onCreate() {
        super.onCreate()
        if (!Python.isStarted()) Python.start(AndroidPlatform(this))
        engine = YtdlpEngineImpl(this)
    }
}
