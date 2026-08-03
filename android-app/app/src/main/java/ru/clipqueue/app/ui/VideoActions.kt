package ru.clipqueue.app.ui

import android.content.Intent
import android.net.Uri
import android.widget.Toast
import androidx.compose.runtime.Composable
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.platform.LocalContext
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch
import ru.clipqueue.app.ApiClient
import ru.clipqueue.app.data.VideoCard
import ru.clipqueue.app.ui.components.CardAction

class VideoActions(
    private val api: ApiClient,
    private val scope: CoroutineScope,
    private val context: android.content.Context,
    private val onOpenVideo: (String) -> Unit,
    private val onRemoved: (String) -> Unit = {},
) {
    fun handle(card: VideoCard, action: CardAction) {
        val id = card.video_id ?: return
        when (action) {
            CardAction.Open -> onOpenVideo(id)
            CardAction.Watched -> scope.launch {
                runCatching { api.patchLibrary(id, mapOf("status" to "watched")) }
                toast("Просмотрено")
                onRemoved(id)
            }
            CardAction.InterestHot -> scope.launch {
                runCatching { api.patchLibrary(id, mapOf("interest" to 2)) }
                toast("Очень интересно")
            }
            CardAction.InterestOk -> scope.launch {
                runCatching { api.patchLibrary(id, mapOf("interest" to 1)) }
                toast("Интересно")
            }
            CardAction.InterestLow -> scope.launch {
                runCatching { api.patchLibrary(id, mapOf("interest" to -1)) }
                toast("Менее интересно")
            }
            CardAction.Dismiss -> scope.launch {
                runCatching { api.deleteLibrary(id) }
                toast("Удалено")
                onRemoved(id)
            }
        }
    }

    fun openYoutube(card: VideoCard) {
        val id = card.video_id ?: return
        scope.launch {
            val url = runCatching { api.openVideo(id).watch_url }.getOrNull()
                ?: card.watch_url
                ?: "https://www.youtube.com/watch?v=$id"
            context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
        }
    }

    private fun toast(msg: String) {
        Toast.makeText(context, msg, Toast.LENGTH_SHORT).show()
    }
}

@Composable
fun rememberVideoActions(
    api: ApiClient,
    onOpenVideo: (String) -> Unit,
    onRemoved: (String) -> Unit = {},
): VideoActions {
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    return VideoActions(api, scope, context, onOpenVideo, onRemoved)
}
