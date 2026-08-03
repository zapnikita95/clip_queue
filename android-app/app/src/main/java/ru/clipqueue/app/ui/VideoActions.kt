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
import ru.clipqueue.app.AppCache
import ru.clipqueue.app.data.VideoCard
import ru.clipqueue.app.ui.components.CardAction

class VideoActions(
    private val api: ApiClient,
    private val scope: CoroutineScope,
    private val context: android.content.Context,
    private val onOpenVideo: (String) -> Unit,
    private val onRemoved: (String) -> Unit = {},
    private val onTag: (VideoCard) -> Unit = {},
    private val onMove: (VideoCard) -> Unit = {},
    private val onInterestDone: () -> Unit = {},
    private val cache: AppCache? = null,
) {
    fun handle(card: VideoCard, action: CardAction) {
        val id = card.video_id ?: return
        when (action) {
            CardAction.Open -> onOpenVideo(id)
            CardAction.Watched -> scope.launch {
                val r = runCatching { api.patchLibrary(id, mapOf("status" to "watched")) }.getOrNull()
                toast(if (r?.ok == true) "Просмотрено" else (r?.error ?: "Ошибка"))
                if (r?.ok == true) {
                    onRemoved(id)
                    cache?.invalidateHome()
                }
            }
            CardAction.InterestHot -> scope.launch {
                val r = runCatching { api.setInterest(id, 2) }.getOrNull()
                toast(if (r?.ok == true) "Очень интересно" else (r?.error ?: "Ошибка"))
                if (r?.ok == true) {
                    cache?.invalidateHome()
                    onInterestDone()
                }
            }
            CardAction.InterestOk -> scope.launch {
                val r = runCatching { api.setInterest(id, 1) }.getOrNull()
                toast(if (r?.ok == true) "Интересно" else (r?.error ?: "Ошибка"))
                if (r?.ok == true) {
                    cache?.invalidateHome()
                    onInterestDone()
                }
            }
            CardAction.InterestLow -> scope.launch {
                val r = runCatching { api.setInterest(id, -1) }.getOrNull()
                toast(if (r?.ok == true) "Менее интересно" else (r?.error ?: "Ошибка"))
                if (r?.ok == true) {
                    cache?.invalidateHome()
                    onInterestDone()
                }
            }
            CardAction.Dismiss -> scope.launch {
                val r = runCatching { api.deleteLibrary(id) }.getOrNull()
                toast(if (r?.ok == true) "Удалено" else (r?.error ?: "Ошибка"))
                if (r?.ok == true) {
                    onRemoved(id)
                    cache?.invalidateAll()
                }
            }
            CardAction.Tag -> onTag(card)
            CardAction.Move -> onMove(card)
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
    onTag: (VideoCard) -> Unit = {},
    onMove: (VideoCard) -> Unit = {},
    onInterestDone: () -> Unit = {},
    cache: AppCache? = null,
): VideoActions {
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    return VideoActions(api, scope, context, onOpenVideo, onRemoved, onTag, onMove, onInterestDone, cache)
}
