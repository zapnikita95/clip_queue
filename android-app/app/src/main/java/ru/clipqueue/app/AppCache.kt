package ru.clipqueue.app

import ru.clipqueue.app.data.ListCard
import ru.clipqueue.app.data.TagDto
import ru.clipqueue.app.data.VideoCard

/** Keeps Лента/Папки warm when switching bottom tabs. */
class AppCache {
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

    @Volatile var home: Home? = null
    @Volatile var folders: Folders? = null

    fun invalidateHome() {
        home = null
    }

    fun invalidateFolders() {
        folders = null
    }

    fun invalidateAll() {
        home = null
        folders = null
    }
}
