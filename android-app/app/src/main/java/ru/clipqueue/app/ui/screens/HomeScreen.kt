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
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.launch
import ru.clipqueue.app.ApiClient
import ru.clipqueue.app.AppCache
import ru.clipqueue.app.ClipQueueApp
import ru.clipqueue.app.data.ListCard
import ru.clipqueue.app.data.TagDto
import ru.clipqueue.app.data.VideoCard
import ru.clipqueue.app.ui.MovePickerDialog
import ru.clipqueue.app.ui.TagPickerDialog
import ru.clipqueue.app.ui.components.BottomBar
import ru.clipqueue.app.ui.components.FolderGrid
import ru.clipqueue.app.ui.components.SectionLabel
import ru.clipqueue.app.ui.components.TagChip
import ru.clipqueue.app.ui.components.VideoRail
import ru.clipqueue.app.ui.rememberVideoActions
import ru.clipqueue.app.ui.theme.CqAccent
import ru.clipqueue.app.ui.theme.CqBg
import ru.clipqueue.app.ui.theme.CqMuted

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    api: ApiClient,
    onOpenVideo: (String) -> Unit,
    onOpenFolder: (ListCard) -> Unit,
    onOpenFolders: () -> Unit,
    onOpenProfile: () -> Unit,
) {
    val appCache = (LocalContext.current.applicationContext as ClipQueueApp).cache
    val cached = remember { appCache.home }

    var loading by remember { mutableStateOf(cached == null) }
    var refreshing by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var recent by remember { mutableStateOf(cached?.recent.orEmpty()) }
    var vibe by remember { mutableStateOf(cached?.vibe.orEmpty()) }
    var fromPlaylists by remember { mutableStateOf(cached?.fromPlaylists.orEmpty()) }
    var topFolders by remember { mutableStateOf(cached?.topFolders.orEmpty()) }
    var tags by remember { mutableStateOf(cached?.tags.orEmpty()) }
    var selectedTagId by remember { mutableStateOf<Int?>(null) }
    var taggedVideos by remember { mutableStateOf<List<VideoCard>>(emptyList()) }
    var taggedFolders by remember { mutableStateOf<List<ListCard>>(emptyList()) }
    var tagCard by remember { mutableStateOf<VideoCard?>(null) }
    var moveCard by remember { mutableStateOf<VideoCard?>(null) }
    val scope = rememberCoroutineScope()

    fun usedTags(list: List<TagDto>) = list.filter { (it.video_count ?: 0) > 0 }

    suspend fun loadHome(initial: Boolean, force: Boolean = false) {
        if (!force && !initial && appCache.home != null && recent.isNotEmpty()) {
            // silent background refresh without blanking UI
            refreshing = true
        } else if (initial && recent.isEmpty()) {
            loading = true
        } else if (force) {
            refreshing = true
        }
        error = null
        try {
            coroutineScope {
                val recentDef = async { api.homeRail("queue") }
                val vibeDef = async { api.homeRail("continue_vibe") }
                val plDef = async { api.homeRail("from_playlists") }
                val listsDef = async { api.lists() }
                val tagsDef = async { runCatching { api.tags(onlyUsed = true) }.getOrNull() }
                recent = recentDef.await().items.orEmpty()
                vibe = vibeDef.await().items.orEmpty()
                fromPlaylists = plDef.await().items.orEmpty()
                topFolders = listsDef.await().lists.orEmpty()
                    .sortedByDescending { it.count ?: 0 }
                    .take(8)
                tags = usedTags(tagsDef.await()?.tags.orEmpty())
                appCache.home = AppCache.Home(
                    recent = recent,
                    vibe = vibe,
                    fromPlaylists = fromPlaylists,
                    topFolders = topFolders,
                    tags = tags,
                )
            }
            val tid = selectedTagId
            if (tid != null) {
                taggedVideos = runCatching {
                    api.library(status = "all", tagId = tid, kind = "all", limit = 60).items.orEmpty()
                }.getOrDefault(emptyList())
                taggedFolders = runCatching { api.lists(tagId = tid).lists.orEmpty() }
                    .getOrDefault(emptyList())
                    .sortedByDescending { it.count ?: 0 }
            }
        } catch (e: Exception) {
            if (recent.isEmpty()) error = e.message ?: "Не удалось загрузить"
        } finally {
            loading = false
            refreshing = false
        }
    }

    val actions = rememberVideoActions(
        api = api,
        onOpenVideo = onOpenVideo,
        onRemoved = { id ->
            recent = recent.filterNot { it.video_id == id }
            vibe = vibe.filterNot { it.video_id == id }
            fromPlaylists = fromPlaylists.filterNot { it.video_id == id }
            taggedVideos = taggedVideos.filterNot { it.video_id == id }
        },
        onTag = { tagCard = it },
        onMove = { moveCard = it },
        onInterestDone = { scope.launch { loadHome(initial = false, force = true) } },
        cache = appCache,
    )

    LaunchedEffect(Unit) {
        if (cached != null) {
            // warm UI already; refresh quietly
            loadHome(initial = false, force = false)
        } else {
            loadHome(initial = true)
        }
    }

    LaunchedEffect(selectedTagId) {
        val tid = selectedTagId
        if (tid == null) {
            taggedVideos = emptyList()
            taggedFolders = emptyList()
        } else {
            taggedVideos = runCatching {
                api.library(status = "all", tagId = tid, kind = "all", limit = 60).items.orEmpty()
            }.getOrDefault(emptyList())
            taggedFolders = runCatching { api.lists(tagId = tid).lists.orEmpty() }
                .getOrDefault(emptyList())
                .sortedByDescending { it.count ?: 0 }
        }
    }

    tagCard?.let { c ->
        TagPickerDialog(api, c, appCache, onDismiss = { tagCard = null }, onChanged = {
            scope.launch { loadHome(initial = false, force = true) }
        })
    }
    moveCard?.let { c ->
        MovePickerDialog(api, c, appCache, onDismiss = { moveCard = null }, onChanged = {
            scope.launch { loadHome(initial = false, force = true) }
        })
    }

    Column(
        modifier = Modifier.fillMaxSize().background(CqBg),
    ) {
        Column(modifier = Modifier.padding(horizontal = 12.dp)) {
            Spacer(Modifier.height(14.dp))
            Text("Clip Queue", style = MaterialTheme.typography.titleLarge)
        }

        when {
            loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = CqAccent)
            }
            error != null && recent.isEmpty() -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text(error.orEmpty(), color = CqAccent)
            }
            else -> PullToRefreshBox(
                isRefreshing = refreshing,
                onRefresh = {
                    scope.launch {
                        runCatching { api.startYoutubeSync(full = false) }
                        loadHome(initial = false, force = true)
                    }
                },
                modifier = Modifier.weight(1f),
            ) {
                LazyColumn(modifier = Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 8.dp)) {
                    if (tags.isNotEmpty()) {
                        item {
                            SectionLabel("Теги", Modifier.padding(horizontal = 12.dp))
                            LazyRow(
                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                                contentPadding = PaddingValues(horizontal = 12.dp),
                            ) {
                                item {
                                    TagChip("Все", selected = selectedTagId == null) { selectedTagId = null }
                                }
                                items(tags, key = { it.id ?: it.name.orEmpty() }) { t ->
                                    val label = listOfNotNull(t.emoji?.takeIf { it.isNotBlank() }, t.name).joinToString(" ")
                                    TagChip(label, selected = selectedTagId == t.id) {
                                        selectedTagId = if (selectedTagId == t.id) null else t.id
                                    }
                                }
                            }
                        }
                    }
                    if (selectedTagId != null) {
                        item {
                            SectionLabel("Папки с тегом", Modifier.padding(horizontal = 12.dp))
                            if (taggedFolders.isEmpty()) {
                                Text("Пусто", color = CqMuted, modifier = Modifier.padding(horizontal = 12.dp))
                            } else {
                                FolderGrid(taggedFolders.take(8), onOpenFolder)
                            }
                        }
                        item {
                            SectionLabel("Видео с тегом", Modifier.padding(horizontal = 12.dp))
                            if (taggedVideos.isEmpty()) {
                                Text("Пусто", color = CqMuted, modifier = Modifier.padding(horizontal = 12.dp))
                            } else {
                                VideoRail(taggedVideos) { c, a -> actions.handle(c, a) }
                            }
                        }
                    } else {
                        item {
                            SectionLabel("Недавно", Modifier.padding(horizontal = 12.dp))
                            if (recent.isEmpty()) Text("Пусто", color = CqMuted, modifier = Modifier.padding(horizontal = 12.dp))
                            else VideoRail(recent) { c, a -> actions.handle(c, a) }
                        }
                        item {
                            SectionLabel("Могут понравиться", Modifier.padding(horizontal = 12.dp))
                            val recs = if (vibe.isNotEmpty()) vibe else fromPlaylists
                            if (recs.isEmpty()) Text("Пусто", color = CqMuted, modifier = Modifier.padding(horizontal = 12.dp))
                            else VideoRail(recs) { c, a -> actions.handle(c, a) }
                        }
                        item {
                            Row(
                                modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp).padding(top = 14.dp, bottom = 8.dp),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Text("ТОП ПАПКИ", style = MaterialTheme.typography.labelSmall, color = CqMuted)
                                Text("все →", color = CqAccent, style = MaterialTheme.typography.bodySmall, modifier = Modifier.clickable(onClick = onOpenFolders))
                            }
                            if (topFolders.isEmpty()) Text("Пусто", color = CqMuted, modifier = Modifier.padding(horizontal = 12.dp))
                            else FolderGrid(topFolders, onOpenFolder)
                            Spacer(Modifier.height(12.dp))
                        }
                    }
                }
            }
        }
        BottomBar(0, onHome = {}, onFolders = onOpenFolders, onProfile = onOpenProfile)
    }
}
