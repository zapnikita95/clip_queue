package ru.clipqueue.app.ui.screens

import android.content.Intent
import android.net.Uri
import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import kotlinx.coroutines.launch
import ru.clipqueue.app.ApiClient
import ru.clipqueue.app.data.VideoCard
import ru.clipqueue.app.ui.components.SectionLabel
import ru.clipqueue.app.ui.components.VideoRail
import ru.clipqueue.app.ui.components.CardAction
import ru.clipqueue.app.ui.rememberVideoActions
import ru.clipqueue.app.ui.theme.CqAccent
import ru.clipqueue.app.ui.theme.CqBg
import ru.clipqueue.app.ui.theme.CqMuted
import ru.clipqueue.app.ui.theme.CqText

@Composable
fun VideoDetailScreen(
    api: ApiClient,
    videoId: String,
    onBack: () -> Unit,
    onOpenVideo: (String) -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var loading by remember { mutableStateOf(true) }
    var item by remember { mutableStateOf<VideoCard?>(null) }
    var similar by remember { mutableStateOf<List<VideoCard>>(emptyList()) }
    val actions = rememberVideoActions(api, onOpenVideo)

    fun reload() {
        scope.launch {
            loading = true
            item = runCatching { api.video(videoId).item }.getOrNull()
            similar = runCatching { api.similar(videoId).items }.getOrNull().orEmpty()
            loading = false
        }
    }

    LaunchedEffect(videoId) { reload() }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(CqBg)
            .padding(horizontal = 20.dp),
    ) {
        Spacer(Modifier.height(14.dp))
        Text(
            "← назад",
            color = CqMuted,
            style = MaterialTheme.typography.bodySmall,
            modifier = Modifier.clickable(onClick = onBack),
        )
        when {
            loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = CqAccent)
            }
            item == null -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("Не найдено", color = CqAccent)
            }
            else -> {
                val v = item!!
                Column(
                    modifier = Modifier
                        .weight(1f)
                        .verticalScroll(rememberScrollState()),
                ) {
                    Spacer(Modifier.height(10.dp))
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .aspectRatio(16f / 9f)
                            .clip(RoundedCornerShape(14.dp)),
                    ) {
                        if (!v.thumb_url.isNullOrBlank()) {
                            AsyncImage(
                                model = v.thumb_url,
                                contentDescription = null,
                                contentScale = ContentScale.Crop,
                                modifier = Modifier.fillMaxSize(),
                            )
                        }
                    }
                    Spacer(Modifier.height(14.dp))
                    Text(v.title.orEmpty(), style = MaterialTheme.typography.titleLarge)
                    Text(
                        listOfNotNull(v.channel_title, v.duration_label, statusLabel(v.status)).joinToString(" · "),
                        style = MaterialTheme.typography.bodySmall,
                        color = CqMuted,
                    )
                    val folderNames = v.in_lists.orEmpty().mapNotNull { it.title?.takeIf { t -> t.isNotBlank() } }
                    val tagNames = v.user_tags.orEmpty().mapNotNull { t ->
                        t.name?.takeIf { it.isNotBlank() }?.let { n ->
                            listOfNotNull(t.emoji?.takeIf { it.isNotBlank() }, n).joinToString(" ")
                        }
                    }
                    if (folderNames.isNotEmpty()) {
                        Spacer(Modifier.height(8.dp))
                        Text(
                            "Папки: ${folderNames.joinToString(", ")}",
                            style = MaterialTheme.typography.bodySmall,
                            color = CqAccent,
                        )
                    }
                    if (tagNames.isNotEmpty()) {
                        Spacer(Modifier.height(4.dp))
                        Text(
                            "Теги: ${tagNames.joinToString(", ")}",
                            style = MaterialTheme.typography.bodySmall,
                            color = CqMuted,
                        )
                    }
                    Spacer(Modifier.height(16.dp))
                    Button(
                        onClick = {
                            scope.launch {
                                val url = runCatching { api.openVideo(videoId).watch_url }.getOrNull()
                                    ?: v.watch_url
                                    ?: "https://www.youtube.com/watch?v=$videoId"
                                context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
                                reload()
                            }
                        },
                        modifier = Modifier.fillMaxWidth().height(48.dp),
                        shape = RoundedCornerShape(12.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = CqAccent, contentColor = CqText),
                    ) { Text("Смотреть на YouTube") }
                    Spacer(Modifier.height(8.dp))
                    OutlinedButton(
                        onClick = {
                            scope.launch {
                                api.patchLibrary(videoId, mapOf("status" to "watched"))
                                Toast.makeText(context, "Просмотрено", Toast.LENGTH_SHORT).show()
                                reload()
                            }
                        },
                        modifier = Modifier.fillMaxWidth().height(48.dp),
                        shape = RoundedCornerShape(12.dp),
                        enabled = v.status != "watched",
                    ) {
                        Text(if (v.status == "watched") "Уже просмотрено" else "Отметить просмотренным")
                    }
                    Spacer(Modifier.height(8.dp))
                    OutlinedButton(
                        onClick = {
                            scope.launch {
                                api.patchLibrary(videoId, mapOf("status" to "in_progress"))
                                Toast.makeText(context, "В начатых", Toast.LENGTH_SHORT).show()
                                reload()
                            }
                        },
                        modifier = Modifier.fillMaxWidth().height(48.dp),
                        shape = RoundedCornerShape(12.dp),
                    ) { Text("Отметить начатым") }
                    Spacer(Modifier.height(8.dp))
                    OutlinedButton(
                        onClick = {
                            scope.launch {
                                api.patchLibrary(videoId, mapOf("status" to "queue"))
                                Toast.makeText(context, "В очереди", Toast.LENGTH_SHORT).show()
                                reload()
                            }
                        },
                        modifier = Modifier.fillMaxWidth().height(48.dp),
                        shape = RoundedCornerShape(12.dp),
                    ) { Text("Вернуть в очередь") }
                    Spacer(Modifier.height(8.dp))
                    OutlinedButton(
                        onClick = {
                            scope.launch {
                                api.deleteLibrary(videoId)
                                Toast.makeText(context, "Удалено", Toast.LENGTH_SHORT).show()
                                onBack()
                            }
                        },
                        modifier = Modifier.fillMaxWidth().height(48.dp),
                        shape = RoundedCornerShape(12.dp),
                    ) { Text("Убрать из библиотеки") }

                    if (similar.isNotEmpty()) {
                        SectionLabel("Похожие из твоих")
                        VideoRail(similar) { card, act ->
                            if (act == CardAction.Open) onOpenVideo(card.video_id.orEmpty())
                            else actions.handle(card, act)
                        }
                    }
                    Spacer(Modifier.height(24.dp))
                }
            }
        }
    }
}

private fun statusLabel(status: String?): String? = when (status) {
    "watched" -> "просмотрено"
    "in_progress" -> "начато"
    "archived" -> "архив"
    "queue" -> "в очереди"
    else -> null
}
