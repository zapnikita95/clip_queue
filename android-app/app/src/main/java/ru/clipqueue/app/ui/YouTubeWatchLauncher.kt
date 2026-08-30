package ru.clipqueue.app.ui

import android.content.Context
import android.content.Intent
import android.net.Uri
import ru.clipqueue.app.push.ProgressParse
import ru.clipqueue.app.push.WatchSessionNotifier

/** Open YouTube externally and pin a local notification for watch progress. */
object YouTubeWatchLauncher {
    fun open(
        context: Context,
        videoId: String,
        watchUrl: String?,
        title: String? = null,
        durationSec: Int? = null,
        progressSec: Int? = null,
    ) {
        val raw = watchUrl?.takeIf { it.isNotBlank() }
            ?: "https://www.youtube.com/watch?v=$videoId"
        val url = ProgressParse.withStartOffset(raw, progressSec)
        runCatching {
            context.startActivity(
                Intent(Intent.ACTION_VIEW, Uri.parse(url)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
            )
        }
        WatchSessionNotifier.show(context, videoId, title, durationSec)
    }
}
