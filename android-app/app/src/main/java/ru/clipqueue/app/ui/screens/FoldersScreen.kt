package ru.clipqueue.app.ui.screens

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import ru.clipqueue.app.ApiClient
import ru.clipqueue.app.data.ListCard
import ru.clipqueue.app.data.TagDto
import ru.clipqueue.app.data.VideoCard
import ru.clipqueue.app.ui.components.BottomBar
import ru.clipqueue.app.ui.components.FilterChip
import ru.clipqueue.app.ui.components.FolderGrid
import ru.clipqueue.app.ui.components.TagChip
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

@Composable
fun FoldersScreen(
    api: ApiClient,
    onBackHome: () -> Unit,
    onOpenFolder: (ListCard) -> Unit,
    onOpenProfile: () -> Unit,
    onOpenVideo: (String) -> Unit,
) {
    var loading by remember { mutableStateOf(true) }
    var folders by remember { mutableStateOf<List<ListCard>>(emptyList()) }
    var tags by remember { mutableStateOf<List<TagDto>>(emptyList()) }
    var selectedTagId by remember { mutableStateOf<Int?>(null) }
    var taggedVideos by remember { mutableStateOf<List<VideoCard>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }
    var query by remember { mutableStateOf("") }
    var sort by remember { mutableStateOf(FolderSort.Count) }
    var minCount by remember { mutableStateOf(0) }
    var expanded by remember { mutableStateOf(setOf<Int>()) }
    val cache = remember { mutableStateMapOf<Int, List<VideoCard>>() }
    val loadingIds = remember { mutableStateMapOf<Int, Boolean>() }

    // Fast: show folder list immediately (covers already in /api/lists). Details on expand only.
    LaunchedEffect(Unit) {
        loading = true
        error = null
        try {
            folders = api.lists().lists.orEmpty()
            tags = runCatching { api.tags().tags.orEmpty() }.getOrDefault(emptyList())
        } catch (e: Exception) {
            error = e.message
        } finally {
            loading = false
        }
    }

    LaunchedEffect(selectedTagId) {
        val tid = selectedTagId ?: run {
            taggedVideos = emptyList()
            return@LaunchedEffect
        }
        taggedVideos = runCatching { api.library(tagId = tid, kind = "all", limit = 80).items.orEmpty() }
            .getOrDefault(emptyList())
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

    Column(modifier = Modifier.fillMaxSize().background(CqBg)) {
        Column(modifier = Modifier.padding(horizontal = 12.dp)) {
            Spacer(Modifier.height(14.dp))
            Text("Папки", style = MaterialTheme.typography.titleLarge)
            Text("сетка · теги · детали по тапу", style = MaterialTheme.typography.bodySmall, color = CqMuted)
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(
                value = query,
                onValueChange = { query = it },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                placeholder = { Text("Найти папку") },
                shape = RoundedCornerShape(12.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = CqAccent,
                    unfocusedBorderColor = CqBorder,
                    focusedTextColor = CqText,
                    unfocusedTextColor = CqText,
                    cursorColor = CqAccent,
                ),
            )
            Spacer(Modifier.height(8.dp))
            LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                item { FilterChip("По числу", sort == FolderSort.Count) { sort = FolderSort.Count } }
                item { FilterChip("А–Я", sort == FolderSort.Name) { sort = FolderSort.Name } }
                item { FilterChip("С видео", minCount == 1) { minCount = if (minCount == 1) 0 else 1 } }
            }
            if (tags.isNotEmpty()) {
                Spacer(Modifier.height(8.dp))
                Text("Фильтр по тегам", style = MaterialTheme.typography.labelSmall, color = CqMuted)
                Spacer(Modifier.height(6.dp))
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
        }

        when {
            loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator(color = CqAccent)
            }
            error != null -> Text(error.orEmpty(), color = CqAccent, modifier = Modifier.padding(12.dp))
            selectedTagId != null -> {
                val tagActions = rememberVideoActions(api, onOpenVideo)
                LazyColumn(modifier = Modifier.weight(1f), contentPadding = PaddingValues(vertical = 8.dp)) {
                    item {
                        Text(
                            "${taggedVideos.size} видео с тегом",
                            color = CqMuted,
                            modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
                        )
                    }
                    if (taggedVideos.isEmpty()) {
                        item { Text("Пусто", color = CqMuted, modifier = Modifier.padding(12.dp)) }
                    } else {
                        items(taggedVideos, key = { it.video_id.orEmpty() }) { card ->
                            VideoListRow(card) { c, a -> tagActions.handle(c, a) }
                        }
                    }
                }
            }
            visible.isEmpty() -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("Ничего не найдено", color = CqMuted)
            }
            else -> LazyColumn(
                modifier = Modifier.weight(1f),
                contentPadding = PaddingValues(vertical = 10.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                item { FolderGrid(visible.take(4), onOpenFolder) }
                items(visible.drop(4), key = { it.id ?: 0 }) { folder ->
                    FolderExpandRow(
                        api = api,
                        folder = folder,
                        expanded = folder.id != null && folder.id in expanded,
                        items = folder.id?.let { cache[it] },
                        isLoadingItems = folder.id?.let { loadingIds[it] == true } == true,
                        onToggle = { id ->
                            expanded = if (id in expanded) expanded - id else expanded + id
                        },
                        onLoaded = { id, items ->
                            cache[id] = items
                            loadingIds[id] = false
                        },
                        onLoading = { id -> loadingIds[id] = true },
                        onOpenFolder = onOpenFolder,
                        onOpenVideo = onOpenVideo,
                    )
                }
            }
        }
        BottomBar(selected = 1, onHome = onBackHome, onFolders = {}, onProfile = onOpenProfile)
    }
}

@Composable
private fun FolderExpandRow(
    api: ApiClient,
    folder: ListCard,
    expanded: Boolean,
    items: List<VideoCard>?,
    isLoadingItems: Boolean,
    onToggle: (Int) -> Unit,
    onLoaded: (Int, List<VideoCard>) -> Unit,
    onLoading: (Int) -> Unit,
    onOpenFolder: (ListCard) -> Unit,
    onOpenVideo: (String) -> Unit,
) {
    val id = folder.id ?: return
    val actions = rememberVideoActions(api, onOpenVideo)

    LaunchedEffect(expanded, id) {
        if (expanded && items == null && !isLoadingItems) {
            onLoading(id)
            val loaded = runCatching { api.listDetail(id).items.orEmpty() }.getOrDefault(emptyList())
            onLoaded(id, loaded)
        }
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
            modifier = Modifier.fillMaxWidth().clickable { onToggle(id) },
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                Text(folder.title.orEmpty(), style = MaterialTheme.typography.titleMedium)
                Text("${folder.count ?: 0} видео", color = CqMuted, style = MaterialTheme.typography.bodySmall)
            }
            Text("открыть", color = CqAccent, style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.clickable { onOpenFolder(folder) }.padding(8.dp))
            Text(if (expanded) "▾" else "▸", color = CqMuted)
        }
        AnimatedVisibility(visible = expanded, enter = fadeIn() + expandVertically(), exit = fadeOut() + shrinkVertically()) {
            Column {
                Spacer(Modifier.height(8.dp))
                when {
                    isLoadingItems || items == null -> Box(Modifier.fillMaxWidth().height(72.dp), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator(color = CqAccent, strokeWidth = 2.dp, modifier = Modifier.height(28.dp))
                    }
                    items.isEmpty() -> Text("Пусто", color = CqMuted)
                    else -> VideoRail(items.take(24)) { card, act -> actions.handle(card, act) }
                }
            }
        }
    }
}

@Composable
fun FolderDetailScreen(
    api: ApiClient,
    folder: ListCard,
    onBack: () -> Unit,
    onOpenVideo: (String) -> Unit,
) {
    var loading by remember { mutableStateOf(true) }
    var items by remember { mutableStateOf<List<VideoCard>>(emptyList()) }
    var title by remember { mutableStateOf(folder.title.orEmpty()) }
    var statusFilter by remember { mutableStateOf(VideoStatusFilter.All) }
    var sortAlpha by remember { mutableStateOf(false) }
    var hideShorts by remember { mutableStateOf(true) }
    var q by remember { mutableStateOf("") }
    var tags by remember { mutableStateOf<List<TagDto>>(emptyList()) }
    var selectedTagId by remember { mutableStateOf<Int?>(null) }

    val actions = rememberVideoActions(api, onOpenVideo) { id -> items = items.filterNot { it.video_id == id } }

    LaunchedEffect(folder.id) {
        val id = folder.id ?: return@LaunchedEffect
        loading = true
        try {
            val r = api.listDetail(id)
            title = r.list?.title ?: title
            items = r.items.orEmpty()
            tags = runCatching { api.tags().tags.orEmpty() }.getOrDefault(emptyList())
        } catch (_: Exception) {
        } finally {
            loading = false
        }
    }

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
            OutlinedTextField(
                value = q, onValueChange = { q = it }, modifier = Modifier.fillMaxWidth(), singleLine = true,
                placeholder = { Text("Поиск в папке") }, shape = RoundedCornerShape(12.dp),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = CqAccent, unfocusedBorderColor = CqBorder,
                    focusedTextColor = CqText, unfocusedTextColor = CqText, cursorColor = CqAccent,
                ),
            )
            Spacer(Modifier.height(8.dp))
            LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                item { FilterChip("Все", statusFilter == VideoStatusFilter.All) { statusFilter = VideoStatusFilter.All } }
                item { FilterChip("Очередь", statusFilter == VideoStatusFilter.Queue) { statusFilter = VideoStatusFilter.Queue } }
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
            loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator(color = CqAccent) }
            filtered.isEmpty() -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Text("Ничего по фильтру", color = CqMuted) }
            else -> LazyColumn(modifier = Modifier.weight(1f), contentPadding = PaddingValues(top = 8.dp, bottom = 16.dp)) {
                items(filtered, key = { it.video_id.orEmpty() }) { card ->
                    VideoListRow(card) { c, a -> actions.handle(c, a) }
                }
            }
        }
    }
}
