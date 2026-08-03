package ru.clipqueue.app

import android.app.Application

class ClipQueueApp : Application() {
    lateinit var session: SessionStore
        private set
    lateinit var api: ApiClient
        private set

    override fun onCreate() {
        super.onCreate()
        session = SessionStore(this)
        api = ApiClient(session)
    }
}

fun Application.clipQueue(): ClipQueueApp = this as ClipQueueApp
