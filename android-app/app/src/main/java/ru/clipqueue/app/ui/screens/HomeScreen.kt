package ru.clipqueue.app.ui.screens

import androidx.compose.foundation.background
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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.launch
import ru.clipqueue.app.ApiClient
import ru.clipqueue.app.data.ListCard
import ru.clipqueue.app.data.VideoCard
import ru.clipqueue.app.ui.components.BottomBar
import ru.clipqueue.app.ui.components.FolderCarousel
import ru.clipqueue.app.ui.components.SectionLabel
import ru.clipqueue.app.ui.components.VideoRail
import ru.clipqueue.app.ui.rememberVideoActions
import ru.clipqueue.app.ui.theme.CqAccent
import ru.clipqueue.app.ui.theme.CqBg
import ru.clipqueue.app.ui.theme.CqMuted

@Composable
fun HomeScreen(
    api: ApiClient,
    onOpenVideo: (String) -> Unit,
    onOpenFolder: (ListCard) -> Unit,
    onOpenFolders: () -> Unit,
    onOpenProfile: () -> Unit,
) {
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    var recent by remember { mutableStateOf<List<VideoCard>>(emptyList()) }
    var vibe by remember { mutableStateOf<List<VideoCard>>(emptyList()) }
    var fromPlaylists by remember { mutableStateOf<List<VideoCard>>(emptyList()) }
    var topFolders by remember { mutableStateOf<List<ListCard>>(emptyList()) }

    val actions = rememberVideoActions(
        api = api,
        onOpenVideo = onOpenVideo,
        onRemoved = { id ->
            recent = recent.filterNot { it.video_id == id }
            vibe = vibe.filterNot { it.video_id == id }
            fromPlaylists = fromPlaylists.filterNot { it.video_id == id }
        },
    )

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
        Text("из твоего", style = MaterialTheme.typography.bodySmall, color = CqMuted)

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
                    SectionLabel("Недавно")
                    if (recent.isEmpty()) Text("Пока пусто", color = CqMuted)
                    else VideoRail(recent) { c, a -> actions.handle(c, a) }
                }
                item {
                    SectionLabel("Могут понравиться")
                    val recs = if (vibe.isNotEmpty()) vibe else fromPlaylists
                    if (recs.isEmpty()) Text("Смотри ролики — появятся рекомендации", color = CqMuted)
                    else VideoRail(recs) { c, a -> actions.handle(c, a) }
                }
                item {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(top = 18.dp, bottom = 10.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text("ТОП ПАПКИ", style = MaterialTheme.typography.labelSmall, color = CqMuted)
                        Text(
                            "все →",
                            style = MaterialTheme.typography.bodySmall,
                            color = CqAccent,
                            modifier = Modifier.clickable(onClick = onOpenFolders),
                        )
                    }
                    if (topFolders.isEmpty()) Text("Папок пока нет", color = CqMuted)
                    else FolderCarousel(topFolders, onOpenFolder, onOpenFolders)
                }
            }
        }
        BottomBar(0, onHome = {}, onFolders = onOpenFolders, onProfile = onOpenProfile)
    }
}
