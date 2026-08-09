package ru.clipqueue.app

import android.app.Application
import coil.ImageLoader
import coil.ImageLoaderFactory
import coil.disk.DiskCache
import coil.memory.MemoryCache
import coil.request.CachePolicy
import okhttp3.OkHttpClient
import ru.clipqueue.app.push.PushRegistrar
import java.util.concurrent.TimeUnit

class ClipQueueApp : Application(), ImageLoaderFactory {
    lateinit var session: SessionStore
        private set
    lateinit var api: ApiClient
        private set
    lateinit var saveHistory: SaveHistoryStore
        private set
    lateinit var cache: AppCache
        private set

    override fun onCreate() {
        super.onCreate()
        session = SessionStore(this)
        api = ApiClient(session)
        saveHistory = SaveHistoryStore(this)
        cache = AppCache(this)
        PushRegistrar.ensureChannel(this)
        if (session.isLoggedIn) {
            PushRegistrar.syncIfLoggedIn(this)
        }
    }

    /**
     * YouTube thumbs send aggressive Cache-Control — ignore and keep a large disk cache
     * so folder re-entry does not re-download every image.
     */
    override fun newImageLoader(): ImageLoader {
        val http = OkHttpClient.Builder()
            .connectTimeout(20, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .build()
        return ImageLoader.Builder(this)
            .okHttpClient(http)
            .crossfade(120)
            .respectCacheHeaders(false)
            .memoryCachePolicy(CachePolicy.ENABLED)
            .diskCachePolicy(CachePolicy.ENABLED)
            .networkCachePolicy(CachePolicy.ENABLED)
            .memoryCache {
                MemoryCache.Builder(this)
                    .maxSizePercent(0.28)
                    .build()
            }
            .diskCache {
                DiskCache.Builder()
                    .directory(cacheDir.resolve("kyro_image_cache"))
                    .maxSizeBytes(512L * 1024L * 1024L)
                    .build()
            }
            .build()
    }
}

fun Application.clipQueue(): ClipQueueApp = this as ClipQueueApp
