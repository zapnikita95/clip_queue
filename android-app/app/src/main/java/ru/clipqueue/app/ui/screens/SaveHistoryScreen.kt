package ru.clipqueue.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
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
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import kotlinx.coroutines.launch
import ru.clipqueue.app.ApiClient
import ru.clipqueue.app.SaveHistoryStore
import ru.clipqueue.app.data.SaveEvent
import ru.clipqueue.app.ui.theme.CqAccent
import ru.clipqueue.app.ui.theme.CqBg
import ru.clipqueue.app.ui.theme.CqBorder
import ru.clipqueue.app.ui.theme.CqElev
import ru.clipqueue.app.ui.theme.CqMuted
import ru.clipqueue.app.ui.theme.CqText

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SaveHistoryScreen(
    api: ApiClient,
    localStore: SaveHistoryStore,
    onBack: () -> Unit,
    onOpenVideo: (String) -> Unit,
) {
    var loading by remember { mutableStateOf(true) }
    var refreshing by remember { mutableStateOf(false) }
    var events by remember { mutableStateOf<List<SaveEvent>>(emptyList()) }
    val scope = rememberCoroutineScope()

    suspend fun load(initial: Boolean) {
        if (initial) loading = true else refreshing = true
        val local = localStore.all()
        val remote = runCatching { api.saveHistory(50).events.orEmpty() }.getOrDefault(emptyList())
        events = mergeEvents(remote, local)
        loading = false
        refreshing = false
    }

    LaunchedEffect(Unit) { load(true) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(CqBg)
            .padding(horizontal = 20.dp),
    ) {
        Spacer(Modifier.height(18.dp))
        Text(
            "Назад",
            color = CqMuted,
            style = MaterialTheme.typography.bodySmall,
            modifier = Modifier.clickable(onClick = onBack),
        )
        Spacer(Modifier.height(6.dp))
        Text("История сохранений", style = MaterialTheme.typography.titleLarge)
        Spacer(Modifier.height(10.dp))

        when {
            loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = CqAccent)
            }
            events.isEmpty() -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("Пусто", color = CqMuted)
            }
            else -> PullToRefreshBox(
                isRefreshing = refreshing,
                onRefresh = { scope.launch { load(false) } },
                modifier = Modifier.weight(1f),
            ) {
                LazyColumn(
                    contentPadding = PaddingValues(bottom = 24.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    items(events, key = { "${it.id}-${it.video_id}-${it.created_at}" }) { ev ->
                        SaveEventCard(ev) {
                            val id = ev.video_id
                            if (!id.isNullOrBlank()) onOpenVideo(id)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun SaveEventCard(ev: SaveEvent, onClick: () -> Unit) {
    val folders = ev.classified_into.orEmpty()
        .mapNotNull { it.list_title?.takeIf { t -> t.isNotBlank() } }
        .ifEmpty { ev.in_lists.orEmpty().mapNotNull { it.title?.takeIf { t -> t.isNotBlank() } } }
    val tags = ev.tags.orEmpty().mapNotNull { t ->
        val name = t.name?.takeIf { it.isNotBlank() } ?: return@mapNotNull null
        listOfNotNull(t.emoji?.takeIf { it.isNotBlank() }, name).joinToString(" ")
    }
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(CqElev, RoundedCornerShape(14.dp))
            .border(1.dp, CqBorder, RoundedCornerShape(14.dp))
            .clickable(onClick = onClick)
            .padding(12.dp),
    ) {
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            if (!ev.thumb_url.isNullOrBlank()) {
                AsyncImage(
                    model = ev.thumb_url,
                    contentDescription = null,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier
                        .width(96.dp)
                        .height(56.dp)
                        .clip(RoundedCornerShape(8.dp)),
                )
            } else {
                Box(
                    Modifier
                        .width(96.dp)
                        .height(56.dp)
                        .clip(RoundedCornerShape(8.dp))
                        .background(CqBorder),
                )
            }
            Column(Modifier.weight(1f)) {
                Text(
                    ev.title.orEmpty().ifBlank { ev.video_id.orEmpty() },
                    style = MaterialTheme.typography.titleMedium,
                    color = CqText,
                    maxLines = 2,
                )
                Text(
                    listOfNotNull(ev.channel_title, ev.created_at, ev.source).joinToString(" · "),
                    style = MaterialTheme.typography.bodySmall,
                    color = CqMuted,
                )
            }
        }
        Spacer(Modifier.height(8.dp))
        if (folders.isNotEmpty()) {
            Text(
                folders.joinToString(", "),
                style = MaterialTheme.typography.bodySmall,
                color = CqAccent,
            )
        }
        if (tags.isNotEmpty()) {
            Text(
                tags.joinToString(", "),
                style = MaterialTheme.typography.bodySmall,
                color = CqMuted,
            )
        }
    }
}

private fun mergeEvents(remote: List<SaveEvent>, local: List<SaveEvent>): List<SaveEvent> {
    val seen = linkedSetOf<String>()
    val out = mutableListOf<SaveEvent>()
    fun key(e: SaveEvent) = "${e.video_id}|${e.created_at}|${e.classify_engine}"
    for (e in remote + local) {
        val k = key(e)
        if (k in seen) continue
        seen += k
        out += e
    }
    return out.sortedByDescending { it.created_at.orEmpty() }
}
