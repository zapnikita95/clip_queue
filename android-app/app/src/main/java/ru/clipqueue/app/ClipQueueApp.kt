package ru.clipqueue.app

import android.app.Application

class ClipQueueApp : Application() {
    lateinit var session: SessionStore
        private set
    lateinit var api: ApiClient
        private set
    lateinit var saveHistory: SaveHistoryStore
        private set

    override fun onCreate() {
        super.onCreate()
        session = SessionStore(this)
        api = ApiClient(session)
        saveHistory = SaveHistoryStore(this)
    }
}

fun Application.clipQueue(): ClipQueueApp = this as ClipQueueApp
