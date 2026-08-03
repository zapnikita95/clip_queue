package ru.clipqueue.app.ui.screens

import android.content.Intent
import android.net.Uri
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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.launch
import ru.clipqueue.app.ApiClient
import ru.clipqueue.app.data.ListCard
import ru.clipqueue.app.data.VideoCard
import ru.clipqueue.app.ui.components.SectionLabel
import ru.clipqueue.app.ui.components.VideoRail
import ru.clipqueue.app.ui.theme.CqAccent
import ru.clipqueue.app.ui.theme.CqBg
import ru.clipqueue.app.ui.theme.CqBorder
import ru.clipqueue.app.ui.theme.CqElev
import ru.clipqueue.app.ui.theme.CqMuted
import ru.clipqueue.app.ui.theme.CqText

@Composable
fun HomeScreen(
    api: ApiClient,
    onOpenFolder: (ListCard) -> Unit,
    onOpenFolders: () -> Unit,
    onOpenProfile: () -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    var recent by remember { mutableStateOf<List<VideoCard>>(emptyList()) }
    var vibe by remember { mutableStateOf<List<VideoCard>>(emptyList()) }
    var fromPlaylists by remember { mutableStateOf<List<VideoCard>>(emptyList()) }
    var topFolders by remember { mutableStateOf<List<ListCard>>(emptyList()) }

    suspend fun openVideo(card: VideoCard) {
        val id = card.video_id ?: return
        val watch = try {
            api.openVideo(id).watch_url
        } catch (_: Exception) {
            null
        } ?: card.watch_url ?: "https://www.youtube.com/watch?v=$id"
        context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(watch)))
    }

    LaunchedEffect(Unit) {
        loading = true
        error = null
        try {
            launch { runCatching { api.startYoutubeSync(full = false) } }
            coroutineScope {
                val recentDef = async { api.homeRail("queue") }
                val vibeDef = async { api.homeRail("continue_vibe") }
                val plDef = async { api.homeRail("from_playlists") }
                val listsDef = async { api.lists() }
                recent = recentDef.await().items.orEmpty()
                vibe = vibeDef.await().items.orEmpty()
                fromPlaylists = plDef.await().items.orEmpty()
                // Top frequent = biggest folders by video count
                topFolders = listsDef.await().lists.orEmpty()
                    .sortedByDescending { it.count ?: 0 }
                    .take(8)
            }
        } catch (e: Exception) {
            error = e.message ?: "Не удалось загрузить"
        } finally {
            loading = false
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(CqBg)
            .padding(horizontal = 20.dp),
    ) {
        Spacer(Modifier.height(18.dp))
        Text("Clip Queue", style = MaterialTheme.typography.titleLarge)
        Text(
            "из твоего · не лента YouTube",
            style = MaterialTheme.typography.bodySmall,
            color = CqMuted,
        )

        when {
            loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = CqAccent)
            }
            error != null -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text(error.orEmpty(), color = CqAccent)
            }
            else -> LazyColumn(
                modifier = Modifier.weight(1f),
                contentPadding = PaddingValues(bottom = 12.dp),
            ) {
                item {
                    SectionLabel("Недавно добавленные")
                    if (recent.isEmpty()) {
                        Text("Пока пусто — поделись роликом из YouTube", color = CqMuted)
                    } else {
                        VideoRail(recent) { scope.launch { openVideo(it) } }
                    }
                }
                item {
                    SectionLabel("Могут понравиться")
                    val recs = if (vibe.isNotEmpty()) vibe else fromPlaylists
                    if (recs.isEmpty()) {
                        Text("Смотри ролики — подтянем вайб", color = CqMuted)
                    } else {
                        VideoRail(recs) { scope.launch { openVideo(it) } }
                    }
                }
                if (fromPlaylists.isNotEmpty() && vibe.isNotEmpty()) {
                    item {
                        SectionLabel("Из плейлистов")
                        VideoRail(fromPlaylists) { scope.launch { openVideo(it) } }
                    }
                }
                item {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(top = 18.dp, bottom = 10.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text(
                            "ТОП ПАПКИ",
                            style = MaterialTheme.typography.labelSmall,
                            color = CqMuted,
                        )
                        Text(
                            "все →",
                            style = MaterialTheme.typography.bodySmall,
                            color = CqAccent,
                            modifier = Modifier.clickable(onClick = onOpenFolders),
                        )
                    }
                    if (topFolders.isEmpty()) {
                        Text("Папки появятся после organize / share", color = CqMuted)
                    } else {
                        FolderCarousel(
                            folders = topFolders,
                            onOpenFolder = onOpenFolder,
                            onSeeAll = onOpenFolders,
                        )
                    }
                }
            }
        }

        BottomBar(selected = 0, onHome = {}, onFolders = onOpenFolders, onProfile = onOpenProfile)
    }
}

@Composable
fun FolderCarousel(
    folders: List<ListCard>,
    onOpenFolder: (ListCard) -> Unit,
    onSeeAll: () -> Unit,
) {
    LazyRow(
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        contentPadding = PaddingValues(end = 8.dp),
    ) {
        items(folders, key = { it.id ?: it.title.orEmpty() }) { folder ->
            Column(
                modifier = Modifier
                    .width(132.dp)
                    .height(88.dp)
                    .background(CqElev, RoundedCornerShape(14.dp))
                    .border(1.dp, CqBorder, RoundedCornerShape(14.dp))
                    .clickable { onOpenFolder(folder) }
                    .padding(14.dp),
                verticalArrangement = Arrangement.SpaceBetween,
            ) {
                Text(
                    text = folder.title.orEmpty(),
                    style = MaterialTheme.typography.titleMedium,
                    color = CqText,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = "${folder.count ?: 0} видео",
                    style = MaterialTheme.typography.bodySmall,
                    color = CqMuted,
                )
            }
        }
        item {
            Column(
                modifier = Modifier
                    .width(100.dp)
                    .height(88.dp)
                    .border(1.dp, CqBorder, RoundedCornerShape(14.dp))
                    .clickable(onClick = onSeeAll)
                    .padding(14.dp),
                verticalArrangement = Arrangement.Center,
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Text("Все", color = CqAccent, style = MaterialTheme.typography.titleMedium)
                Text("папки", color = CqMuted, style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
fun BottomBar(
    selected: Int,
    onHome: () -> Unit,
    onFolders: () -> Unit,
    onProfile: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 14.dp),
        horizontalArrangement = Arrangement.SpaceAround,
    ) {
        listOf(
            Triple(0, "Лента", onHome),
            Triple(1, "Папки", onFolders),
            Triple(2, "Профиль", onProfile),
        ).forEach { (idx, label, action) ->
            Text(
                text = label,
                color = if (selected == idx) CqAccent else CqMuted,
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.clickable(onClick = action),
            )
        }
    }
}
