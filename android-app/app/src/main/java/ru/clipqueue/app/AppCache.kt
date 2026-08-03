package ru.clipqueue.app

import android.content.Context
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import ru.clipqueue.app.data.ListCard
import ru.clipqueue.app.data.TagDto
import ru.clipqueue.app.data.VideoCard
import java.io.File
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.Executors

/**
 * In-memory + on-disk cache. Survives process death.
 * Network refresh only when UI explicitly asks (pull-to-refresh).
 */
class AppCache(private val context: Context) {
    data class Home(
        val recent: List<VideoCard> = emptyList(),
        val vibe: List<VideoCard> = emptyList(),
        val fromPlaylists: List<VideoCard> = emptyList(),
        val topFolders: List<ListCard> = emptyList(),
        val tags: List<TagDto> = emptyList(),
    )

    data class Folders(
        val folders: List<ListCard> = emptyList(),
        val tags: List<TagDto> = emptyList(),
    )

    private data class DiskSnapshot(
        val home: Home? = null,
        val folders: Folders? = null,
        val folderItems: Map<String, List<VideoCard>> = emptyMap(),
    )

    private val gson = Gson()
    private val io = Executors.newSingleThreadExecutor()
    private val snapFile: File
        get() = File(context.filesDir, "kyro_library_cache.json")

    @Volatile var home: Home? = null
        set(value) {
            field = value
            schedulePersist()
        }

    @Volatile var folders: Folders? = null
        set(value) {
            field = value
            schedulePersist()
        }

    private val folderItems = ConcurrentHashMap<Int, List<VideoCard>>()

    init {
        loadFromDisk()
    }

    fun folderItems(listId: Int): List<VideoCard>? = folderItems[listId]

    fun putFolderItems(listId: Int, items: List<VideoCard>) {
        folderItems[listId] = items
        schedulePersist()
    }

    fun patchFolderItems(listId: Int, transform: (List<VideoCard>) -> List<VideoCard>) {
        val cur = folderItems[listId] ?: return
        folderItems[listId] = transform(cur)
        schedulePersist()
    }

    fun removeVideoEverywhere(videoId: String) {
        val keys = folderItems.keys.toList()
        for (k in keys) {
            val cur = folderItems[k] ?: continue
            folderItems[k] = cur.filterNot { it.video_id == videoId }
        }
        home = home?.let { h ->
            h.copy(
                recent = h.recent.filterNot { it.video_id == videoId },
                vibe = h.vibe.filterNot { it.video_id == videoId },
                fromPlaylists = h.fromPlaylists.filterNot { it.video_id == videoId },
            )
        }
        schedulePersist()
    }

    fun invalidateHome() {
        // Keep disk warm — UI may still show; next pull refreshes.
    }

    fun invalidateFolders() {
        // Keep folder list + items on disk until pull-to-refresh replaces them.
    }

    fun invalidateFolder(listId: Int) {
        // no-op for cold open; pull-to-refresh calls putFolderItems
    }

    fun invalidateAll() {
        home = null
        folders = null
        folderItems.clear()
        io.execute {
            runCatching { snapFile.delete() }
        }
    }

    private fun schedulePersist() {
        io.execute { persistNow() }
    }

    @Synchronized
    private fun persistNow() {
        try {
            val snap = DiskSnapshot(
                home = home,
                folders = folders,
                folderItems = folderItems.entries.associate { it.key.toString() to it.value },
            )
            val tmp = File(snapFile.parentFile, "${snapFile.name}.tmp")
            tmp.writeText(gson.toJson(snap))
            if (!tmp.renameTo(snapFile)) {
                tmp.copyTo(snapFile, overwrite = true)
                tmp.delete()
            }
        } catch (_: Exception) {
        }
    }

    @Synchronized
    private fun loadFromDisk() {
        try {
            if (!snapFile.exists()) return
            val text = snapFile.readText()
            if (text.isBlank()) return
            val type = object : TypeToken<DiskSnapshot>() {}.type
            val snap = gson.fromJson<DiskSnapshot>(text, type) ?: return
            home = snap.home
            folders = snap.folders
            folderItems.clear()
            snap.folderItems.forEach { (k, v) ->
                k.toIntOrNull()?.let { folderItems[it] = v }
            }
        } catch (_: Exception) {
        }
    }
}
