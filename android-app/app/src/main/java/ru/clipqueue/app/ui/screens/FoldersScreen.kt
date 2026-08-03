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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Sort
import androidx.compose.material.icons.filled.FilterList
import androidx.compose.material.icons.filled.Videocam
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
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
import ru.clipqueue.app.ui.components.FilterChip
import ru.clipqueue.app.ui.components.FolderGrid
import ru.clipqueue.app.ui.components.SearchBarWithMic
import ru.clipqueue.app.ui.components.TagChip
import ru.clipqueue.app.ui.components.ToolIconButton
import ru.clipqueue.app.ui.components.VideoListRow
import ru.clipqueue.app.ui.components.VideoRail
import ru.clipqueue.app.ui.rememberVideoActions
import ru.clipqueue.app.ui.theme.CqAccent
import ru.clipqueue.app.ui.theme.CqBg
import ru.clipqueue.app.ui.theme.CqBorder
import ru.clipqueue.app.ui.theme.CqElev
import ru.clipqueue.app.ui.theme.CqMuted
import ru.clipqueue.app.ui.theme.CqText

private enum class FolderSort { Count, Name, EmptyLast }
private enum class VideoStatusFilter { All, Queue, InProgress, Watched }

private const val TOP_CAROUSEL_COUNT = 5

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FoldersScreen(
    api: ApiClient,
    onBackHome: () -> Unit,
    onOpenFolder: (ListCard) -> Unit,
    onOpenProfile: () -> Unit,
    onOpenVideo: (String) -> Unit,
) {
    val appCache = (LocalContext.current.applicationContext as ClipQueueApp).cache
    val cached = remember { appCache.folders }
    val scope = rememberCoroutineScope()

    var loading by remember { mutableStateOf(cached == null) }
    var refreshing by remember { mutableStateOf(false) }
    var folders by remember { mutableStateOf(cached?.folders.orEmpty()) }
    var tags by remember { mutableStateOf(cached?.tags.orEmpty()) }
    var selectedTagId by remember { mutableStateOf<Int?>(null) }
    var taggedVideos by remember { mutableStateOf<List<VideoCard>>(emptyList()) }
    var taggedFolders by remember { mutableStateOf<List<ListCard>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }
    var query by remember { mutableStateOf("") }
    var sort by remember { mutableStateOf(FolderSort.Count) }
    var minCount by remember { mutableStateOf(0) }
    var sortMenu by remember { mutableStateOf(false) }
    var filterMenu by remember { mutableStateOf(false) }
    var tagCard by remember { mutableStateOf<VideoCard?>(null) }
    var moveCard by remember { mutableStateOf<VideoCard?>(null) }

    fun usedTags(list: List<TagDto>) = list.filter { (it.video_count ?: 0) > 0 }

    /** Network only when force=true (pull-to-refresh). */
    suspend fun loadFolders(force: Boolean) {
        if (!force) {
            val warm = appCache.folders
            if (warm != null) {
                folders = warm.folders
                tags = warm.tags
                loading = false
                return
            }
            if (folders.isEmpty()) loading = true
        } else {
            refreshing = true
        }
        error = null
        try {
            folders = api.lists().lists.orEmpty()
            val used = usedTags(runCatching { api.tags(onlyUsed = true) }.getOrNull()?.tags.orEmpty())
            tags = used.ifEmpty {
                usedTags(runCatching { api.tags(onlyUsed = false) }.getOrNull()?.tags.orEmpty())
            }
            appCache.folders = AppCache.Folders(folders = folders, tags = tags)
            folders.sortedByDescending { it.count ?: 0 }.take(TOP_CAROUSEL_COUNT).forEach { f ->
                val id = f.id ?: return@forEach
                runCatching {
                    appCache.putFolderItems(id, api.listDetail(id).items.orEmpty())
                }
            }
        } catch (e: Exception) {
            if (folders.isEmpty()) error = e.message
        } finally {
            loading = false
            refreshing = false
        }
    }

    LaunchedEffect(Unit) {
        if (appCache.folders != null) {
            folders = appCache.folders!!.folders
            tags = appCache.folders!!.tags
            loading = false
        } else {
            loadFolders(force = true)
        }
    }

    LaunchedEffect(selectedTagId) {
        val tid = selectedTagId ?: run {
            taggedVideos = emptyList()
            taggedFolders = emptyList()
            return@LaunchedEffect
        }
        taggedFolders = runCatching { api.lists(tagId = tid).lists.orEmpty() }
            .getOrDefault(emptyList())
            .sortedByDescending { it.count ?: 0 }
        taggedVideos = runCatching {
            api.library(status = "all", tagId = tid, kind = "all", limit = 80).items.orEmpty()
        }.getOrDefault(emptyList())
    }

    val visible = remember(folders, query, sort, minCount) {
        var list = folders.filter { (it.count ?: 0) >= minCount }
        if (query.isNotBlank()) {
            val q = query.trim().lowercase()
            list = list.filter { it.title.orEmpty().lowercase().contains(q) }
        }
        when (sort) {
            FolderSort.Count -> list.sortedByDescending { it.count ?: 0 }
            FolderSort.Name -> list.sortedBy { it.title.orEmpty().lowercase() }
            FolderSort.EmptyLast -> list.sortedWith(
                compareBy<ListCard> { (it.count ?: 0) == 0 }.thenByDescending { it.count ?: 0 },
            )
        }
    }

    val topCarousel = remember(visible) { visible.take(TOP_CAROUSEL_COUNT) }
    val restGrid = remember(visible) { visible.drop(TOP_CAROUSEL_COUNT) }

    val actions = rememberVideoActions(
        api = api,
        onOpenVideo = onOpenVideo,
        onRemoved = { id ->
            taggedVideos = taggedVideos.filterNot { it.video_id == id }
            appCache.removeVideoEverywhere(id)
        },
        onTag = { tagCard = it },
        onMove = { moveCard = it },
        cache = appCache,
    )

    val sortLabel = when (sort) {
        FolderSort.Count -> "По числу"
        FolderSort.Name -> "А–Я"
        FolderSort.EmptyLast -> "Пустые вниз"
    }

    tagCard?.let { c -> TagPickerDialog(api, c, appCache, onDismiss = { tagCard = null }) }
    moveCard?.let { c ->
        MovePickerDialog(api, c, appCache, onDismiss = { moveCard = null }, onChanged = {
            scope.launch { loadFolders(force = true) }
        })
    }

    Column(modifier = Modifier.fillMaxSize().background(CqBg)) {
        Column(modifier = Modifier.padding(horizontal = 12.dp)) {
            Spacer(Modifier.height(14.dp))
            Text("Папки", style = MaterialTheme.typography.titleLarge)
            Spacer(Modifier.height(10.dp))
            SearchBarWithMic(value = query, onValueChange = { query = it }, placeholder = "Найти папку")
            Spacer(Modifier.height(10.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Box {
                    ToolIconButton(label = sortLabel, selected = true, onClick = { sortMenu = true }) {
                        Icon(Icons.AutoMirrored.Filled.Sort, null, tint = CqText, modifier = Modifier.size(16.dp))
                    }
                    DropdownMenu(expanded = sortMenu, onDismissRequest = { sortMenu = false }) {
                        DropdownMenuItem(text = { Text("По числу") }, onClick = { sort = FolderSort.Count; sortMenu = false })
                        DropdownMenuItem(text = { Text("А–Я") }, onClick = { sort = FolderSort.Name; sortMenu = false })
                        DropdownMenuItem(text = { Text("Пустые вниз") }, onClick = { sort = FolderSort.EmptyLast; sortMenu = false })
                    }
                }
                Box {
                    ToolIconButton(
                        label = if (minCount == 1) "С видео" else "Фильтр",
                        selected = minCount == 1 || filterMenu,
                        onClick = { filterMenu = true },
                    ) {
                        Icon(
                            if (minCount == 1) Icons.Default.Videocam else Icons.Default.FilterList,
                            null,
                            tint = if (minCount == 1) CqText else CqMuted,
                            modifier = Modifier.size(16.dp),
                        )
                    }
                    DropdownMenu(expanded = filterMenu, onDismissRequest = { filterMenu = false }) {
                        DropdownMenuItem(
                            text = { Text(if (minCount == 1) "Все папки" else "Только с видео") },
                            onClick = { minCount = if (minCount == 1) 0 else 1; filterMenu = false },
                        )
                    }
                }
            }
            Spacer(Modifier.height(12.dp))
            Text("Теги", style = MaterialTheme.typography.labelSmall, color = CqMuted)
            Spacer(Modifier.height(6.dp))
            if (tags.isEmpty()) {
                Text("Нет тегов", color = CqMuted, style = MaterialTheme.typography.bodySmall)
            } else {
                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    item { TagChip("Все", selectedTagId == null) { selectedTagId = null } }
                    items(tags, key = { it.id ?: 0 }) { t ->
                        val label = listOfNotNull(t.emoji?.takeIf { it.isNotBlank() }, t.name).joinToString(" ")
                        TagChip(label, selectedTagId == t.id) {
                            selectedTagId = if (selectedTagId == t.id) null else t.id
                        }
                    }
                }
            }
            Spacer(Modifier.height(14.dp))
        }

        when {
            loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = CqAccent)
            }
            error != null && folders.isEmpty() -> Text(error.orEmpty(), color = CqAccent, modifier = Modifier.padding(12.dp))
            selectedTagId != null -> LazyColumn(
                modifier = Modifier.weight(1f),
                contentPadding = PaddingValues(top = 4.dp, bottom = 8.dp),
            ) {
                item {
                    Text("Папки", style = MaterialTheme.typography.labelSmall, color = CqMuted, modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp))
                }
                if (taggedFolders.isEmpty()) {
                    item { Text("Пусто", color = CqMuted, modifier = Modifier.padding(12.dp)) }
                } else {
                    item { FolderGrid(taggedFolders, onOpenFolder) }
                }
                item {
                    Text("${taggedVideos.size} видео", color = CqMuted, modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp))
                }
                if (taggedVideos.isEmpty()) {
                    item { Text("Пусто", color = CqMuted, modifier = Modifier.padding(12.dp)) }
                } else {
                    items(taggedVideos, key = { it.video_id.orEmpty() }) { card ->
                        VideoListRow(card) { c, a -> actions.handle(c, a) }
                    }
                }
            }
            visible.isEmpty() -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("Ничего не найдено", color = CqMuted)
            }
            else -> PullToRefreshBox(
                isRefreshing = refreshing,
                onRefresh = { scope.launch { loadFolders(force = true) } },
                modifier = Modifier.weight(1f),
            ) {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(top = 4.dp, bottom = 10.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    items(topCarousel, key = { "top-${it.id}" }) { folder ->
                        FolderCarouselBlock(
                            api = api,
                            folder = folder,
                            appCache = appCache,
                            forceRefreshTick = refreshing,
                            onOpenFolder = onOpenFolder,
                            onOpenVideo = onOpenVideo,
                            onTag = { tagCard = it },
                            onMove = { moveCard = it },
                        )
                    }
                    if (restGrid.isNotEmpty()) {
                        item {
                            Text("Все папки", style = MaterialTheme.typography.labelSmall, color = CqMuted, modifier = Modifier.padding(horizontal = 12.dp, vertical = 4.dp))
                            FolderGrid(restGrid, onOpenFolder)
                        }
                    }
                }
            }
        }
        BottomBar(selected = 1, onHome = onBackHome, onFolders = {}, onProfile = onOpenProfile)
    }
}

@Composable
private fun FolderCarouselBlock(
    api: ApiClient,
    folder: ListCard,
    appCache: AppCache,
    forceRefreshTick: Boolean,
    onOpenFolder: (ListCard) -> Unit,
    onOpenVideo: (String) -> Unit,
    onTag: (VideoCard) -> Unit,
    onMove: (VideoCard) -> Unit,
) {
    val id = folder.id ?: return
    val cachedItems = remember(id) { appCache.folderItems(id) }
    var items by remember(id) { mutableStateOf(cachedItems) }
    var isLoadingItems by remember(id) { mutableStateOf(cachedItems == null) }

    val actions = rememberVideoActions(
        api = api,
        onOpenVideo = onOpenVideo,
        onTag = onTag,
        onMove = onMove,
        onRemoved = { vid ->
            items = items?.filterNot { it.video_id == vid }
            appCache.removeVideoEverywhere(vid)
        },
        cache = appCache,
    )

    LaunchedEffect(id, forceRefreshTick) {
        val warm = appCache.folderItems(id)
        if (warm != null && !forceRefreshTick) {
            items = warm
            isLoadingItems = false
            return@LaunchedEffect
        }
        if (warm == null) isLoadingItems = true
        val loaded = runCatching { api.listDetail(id).items.orEmpty() }.getOrDefault(warm.orEmpty())
        items = loaded
        appCache.putFolderItems(id, loaded)
        isLoadingItems = false
    }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 12.dp)
            .background(CqElev, RoundedCornerShape(14.dp))
            .border(1.dp, CqBorder, RoundedCornerShape(14.dp))
            .padding(12.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().clickable { onOpenFolder(folder) },
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                Text(folder.title.orEmpty(), style = MaterialTheme.typography.titleMedium)
                Text("${folder.count ?: 0} видео", color = CqMuted, style = MaterialTheme.typography.bodySmall)
            }
            Text("открыть →", color = CqAccent, style = MaterialTheme.typography.bodySmall)
        }
        Spacer(Modifier.height(8.dp))
        val current = items
        when {
            isLoadingItems || current == null -> Box(
                Modifier.fillMaxWidth().height(100.dp),
                contentAlignment = Alignment.Center,
            ) {
                CircularProgressIndicator(color = CqAccent, strokeWidth = 2.dp, modifier = Modifier.height(28.dp))
            }
            current.isEmpty() -> Text("Пусто", color = CqMuted)
            else -> VideoRail(current.take(24)) { card, act -> actions.handle(card, act) }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FolderDetailScreen(
    api: ApiClient,
    folder: ListCard,
    onBack: () -> Unit,
    onOpenVideo: (String) -> Unit,
) {
    val appCache = (LocalContext.current.applicationContext as ClipQueueApp).cache
    val id = folder.id
    val warm = remember(id) { id?.let { appCache.folderItems(it) } }
    val scope = rememberCoroutineScope()

    var loading by remember { mutableStateOf(warm == null) }
    var refreshing by remember { mutableStateOf(false) }
    var items by remember { mutableStateOf(warm.orEmpty()) }
    var title by remember { mutableStateOf(folder.title.orEmpty()) }
    var statusFilter by remember { mutableStateOf(VideoStatusFilter.All) }
    var sortAlpha by remember { mutableStateOf(false) }
    var hideShorts by remember { mutableStateOf(true) }
    var q by remember { mutableStateOf("") }
    var tags by remember { mutableStateOf<List<TagDto>>(emptyList()) }
    var selectedTagId by remember { mutableStateOf<Int?>(null) }
    var tagCard by remember { mutableStateOf<VideoCard?>(null) }
    var moveCard by remember { mutableStateOf<VideoCard?>(null) }

    val actions = rememberVideoActions(
        api = api,
        onOpenVideo = onOpenVideo,
        onRemoved = { vid ->
            items = items.filterNot { it.video_id == vid }
            appCache.removeVideoEverywhere(vid)
        },
        onTag = { tagCard = it },
        onMove = { moveCard = it },
        cache = appCache,
    )

    suspend fun loadDetail(force: Boolean) {
        val listId = id ?: return
        if (!force) {
            val cached = appCache.folderItems(listId)
            if (cached != null) {
                items = cached
                loading = false
                return
            }
            loading = true
        } else {
            refreshing = true
        }
        try {
            val r = api.listDetail(listId)
            title = r.list?.title ?: title
            items = r.items.orEmpty()
            appCache.putFolderItems(listId, items)
            tags = runCatching { api.tags(onlyUsed = true) }.getOrNull()?.tags.orEmpty()
                .filter { (it.video_count ?: 0) > 0 }
        } catch (_: Exception) {
        } finally {
            loading = false
            refreshing = false
        }
    }

    LaunchedEffect(folder.id) {
        loadDetail(force = false)
    }

    tagCard?.let { c -> TagPickerDialog(api, c, appCache, onDismiss = { tagCard = null }) }
    moveCard?.let { c -> MovePickerDialog(api, c, appCache, onDismiss = { moveCard = null }) { } }

    fun isShort(v: VideoCard): Boolean {
        val sec = v.duration_sec
        return sec != null && sec > 0 && sec <= 180
    }

    val filtered = remember(items, statusFilter, sortAlpha, hideShorts, q, selectedTagId) {
        var list = items
        if (hideShorts) list = list.filterNot { isShort(it) }
        list = when (statusFilter) {
            VideoStatusFilter.All -> list
            VideoStatusFilter.Queue -> list.filter { it.status == null || it.status == "queue" }
            VideoStatusFilter.InProgress -> list.filter { it.status == "in_progress" }
            VideoStatusFilter.Watched -> list.filter { it.status == "watched" }
        }
        if (selectedTagId != null) {
            list = list.filter { card -> card.user_tags.orEmpty().any { it.id == selectedTagId } }
        }
        if (q.isNotBlank()) {
            val qq = q.trim().lowercase()
            list = list.filter { "${it.title} ${it.channel_title}".lowercase().contains(qq) }
        }
        if (sortAlpha) list.sortedBy { it.title.orEmpty().lowercase() } else list
    }

    Column(modifier = Modifier.fillMaxSize().background(CqBg)) {
        Column(modifier = Modifier.padding(horizontal = 12.dp)) {
            Spacer(Modifier.height(14.dp))
            Text("← все папки", color = CqMuted, style = MaterialTheme.typography.bodySmall, modifier = Modifier.clickable(onClick = onBack))
            Spacer(Modifier.height(6.dp))
            Text(title, style = MaterialTheme.typography.titleLarge)
            Text("${filtered.size} / ${items.size}", style = MaterialTheme.typography.bodySmall, color = CqMuted)
            Spacer(Modifier.height(8.dp))
            SearchBarWithMic(value = q, onValueChange = { q = it }, placeholder = "Поиск в папке")
            Spacer(Modifier.height(8.dp))
            LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                item { FilterChip("Все", statusFilter == VideoStatusFilter.All) { statusFilter = VideoStatusFilter.All } }
                item { FilterChip("Сохранённые", statusFilter == VideoStatusFilter.Queue) { statusFilter = VideoStatusFilter.Queue } }
                item { FilterChip("Начатые", statusFilter == VideoStatusFilter.InProgress) { statusFilter = VideoStatusFilter.InProgress } }
                item { FilterChip("Просмотренные", statusFilter == VideoStatusFilter.Watched) { statusFilter = VideoStatusFilter.Watched } }
                item { FilterChip(if (hideShorts) "Без шортов" else "Со шортами", hideShorts) { hideShorts = !hideShorts } }
            }
            if (tags.isNotEmpty()) {
                Spacer(Modifier.height(8.dp))
                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    item { TagChip("Все теги", selectedTagId == null) { selectedTagId = null } }
                    items(tags, key = { it.id ?: 0 }) { t ->
                        val label = listOfNotNull(t.emoji?.takeIf { it.isNotBlank() }, t.name).joinToString(" ")
                        TagChip(label, selectedTagId == t.id) {
                            selectedTagId = if (selectedTagId == t.id) null else t.id
                        }
                    }
                }
            }
        }
        when {
            loading && items.isEmpty() -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = CqAccent)
            }
            else -> PullToRefreshBox(
                isRefreshing = refreshing,
                onRefresh = { scope.launch { loadDetail(force = true) } },
                modifier = Modifier.weight(1f),
            ) {
                if (filtered.isEmpty()) {
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Text("Ничего по фильтру", color = CqMuted)
                    }
                } else {
                    LazyColumn(
                        modifier = Modifier.fillMaxSize(),
                        contentPadding = PaddingValues(top = 8.dp, bottom = 16.dp),
                    ) {
                        items(filtered, key = { it.video_id.orEmpty() }) { card ->
                            VideoListRow(card) { c, a -> actions.handle(c, a) }
                        }
                    }
                }
            }
        }
    }
}
