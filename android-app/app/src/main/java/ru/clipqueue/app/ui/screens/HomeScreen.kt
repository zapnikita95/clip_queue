package ru.clipqueue.app.ui.screens

import androidx.activity.compose.BackHandler
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
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.zIndex
import android.widget.Toast
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull
import ru.clipqueue.app.data.LightPlanResponse
import ru.clipqueue.app.data.NowResponse
import ru.clipqueue.app.ApiClient
import ru.clipqueue.app.AppCache
import ru.clipqueue.app.ClipQueueApp
import ru.clipqueue.app.data.ListCard
import ru.clipqueue.app.data.NowMoodDto
import ru.clipqueue.app.data.NowSlotDto
import ru.clipqueue.app.data.TagDto
import ru.clipqueue.app.data.VideoCard
import ru.clipqueue.app.ui.MovePickerDialog
import ru.clipqueue.app.ui.TagPickerDialog
import ru.clipqueue.app.ui.components.BottomBar
import ru.clipqueue.app.ui.components.EditableFolderGrid
import ru.clipqueue.app.ui.components.FolderGrid
import ru.clipqueue.app.ui.components.FolderRemoveDialog
import ru.clipqueue.app.ui.components.FolderTrashZone
import ru.clipqueue.app.ui.components.SectionLabel
import ru.clipqueue.app.ui.components.TagChip
import ru.clipqueue.app.ui.components.VideoRail
import ru.clipqueue.app.ui.components.VideoSpine
import ru.clipqueue.app.ui.rememberVideoActions
import ru.clipqueue.app.ui.theme.CqAccent
import ru.clipqueue.app.ui.theme.CqBg
import ru.clipqueue.app.ui.theme.CqBorder
import ru.clipqueue.app.ui.theme.CqElev
import ru.clipqueue.app.ui.theme.CqMuted
import ru.clipqueue.app.ui.theme.CqText
import ru.clipqueue.app.ui.theme.KyroBrandStyle
import ru.clipqueue.app.ui.theme.KyroFont

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    api: ApiClient,
    onOpenVideo: (String) -> Unit,
    onOpenFolder: (ListCard) -> Unit,
    onOpenFolders: () -> Unit,
    onOpenProfile: () -> Unit,
    onOpenToday: () -> Unit = {},
    onOpenSearch: () -> Unit = {},
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
    var nowSlot by remember { mutableStateOf("any") }
    var nowMood by remember { mutableStateOf("") }
    var nowPicks by remember { mutableStateOf(cached?.nowPicks.orEmpty()) }
    var nowSuggestions by remember { mutableStateOf(cached?.nowSuggestions.orEmpty()) }
    var nowSlots by remember { mutableStateOf(cached?.nowSlots.orEmpty()) }
    var nowMoods by remember { mutableStateOf(cached?.nowMoods.orEmpty()) }
    var nowMeta by remember { mutableStateOf(cached?.nowMeta.orEmpty()) }
    var planTonight by remember { mutableStateOf(cached?.planTonight.orEmpty()) }
    var planSuggestTonight by remember { mutableStateOf(cached?.planSuggestTonight.orEmpty()) }
    // Warm cache ⇒ treat as loaded so tab re-entry never flashes «Подбираем…».
    var nowLoaded by remember {
        mutableStateOf(cached?.nowReady == true || !cached?.nowPicks.isNullOrEmpty())
    }
    var planLoaded by remember {
        mutableStateOf(
            cached?.planReady == true ||
                !cached?.planTonight.isNullOrEmpty() ||
                !cached?.planSuggestTonight.isNullOrEmpty(),
        )
    }
    var tagCard by remember { mutableStateOf<VideoCard?>(null) }
    var moveCard by remember { mutableStateOf<VideoCard?>(null) }
    var folderEdit by remember { mutableStateOf(false) }
    var trashHot by remember { mutableStateOf(false) }
    var trashBounds by remember { mutableStateOf<Rect?>(null) }
    var removeTarget by remember { mutableStateOf<ListCard?>(null) }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current

    BackHandler(enabled = folderEdit) {
        folderEdit = false
        trashHot = false
    }

    fun usedTags(list: List<TagDto>) = list.filter { (it.video_count ?: 0) > 0 }

    fun persistHomeSnapshot() {
        val prev = appCache.home
        appCache.home = AppCache.Home(
            recent = recent.ifEmpty { prev?.recent.orEmpty() },
            vibe = vibe.ifEmpty { prev?.vibe.orEmpty() },
            fromPlaylists = fromPlaylists.ifEmpty { prev?.fromPlaylists.orEmpty() },
            topFolders = topFolders.ifEmpty { prev?.topFolders.orEmpty() },
            tags = tags.ifEmpty { prev?.tags.orEmpty() },
            nowPicks = nowPicks,
            nowSuggestions = nowSuggestions,
            nowSlots = nowSlots,
            nowMoods = nowMoods,
            nowMeta = nowMeta,
            planTonight = planTonight,
            planSuggestTonight = planSuggestTonight,
            nowReady = nowLoaded,
            planReady = planLoaded,
        )
    }

    fun applyNowResponse(now: NowResponse?) {
        if (now == null) {
            nowLoaded = true
            persistHomeSnapshot()
            return
        }
        val started = now.started.orEmpty()
        val picks = now.picks.orEmpty()
        val seen = picks.mapNotNull { it.video_id }.toSet()
        var merged = started.filter { it.video_id !in seen } + picks
        val suggestions = now.suggestions.orEmpty()
        // Never leave «Сейчас» blank when backend still has nudges
        if (merged.isEmpty() && suggestions.isNotEmpty()) {
            merged = suggestions
            nowSuggestions = emptyList()
        } else {
            val mergedIds = merged.mapNotNull { it.video_id }.toSet()
            nowSuggestions = suggestions.filter { it.video_id !in mergedIds }
        }
        nowPicks = merged
        if (now.slots.orEmpty().isNotEmpty()) nowSlots = now.slots.orEmpty()
        if (now.moods.orEmpty().isNotEmpty()) nowMoods = now.moods.orEmpty()
        val day = now.daypart_label?.takeIf { it.isNotBlank() }
        nowMeta = listOfNotNull(day, now.slot_label?.takeIf { it.isNotBlank() }).joinToString(" · ")
        nowLoaded = true
        persistHomeSnapshot()
    }

    fun applyPlanResponse(plan: LightPlanResponse?) {
        planTonight = plan?.tonight.orEmpty()
        planSuggestTonight = plan?.suggest_tonight.orEmpty()
        planLoaded = true
        persistHomeSnapshot()
    }

    suspend fun loadNow(slot: String = nowSlot, mood: String = nowMood) {
        val now = withTimeoutOrNull(12_000) {
            runCatching { api.homeNow(slot = slot, mood = mood, limit = 6) }.getOrNull()
        }
        applyNowResponse(now)
    }

    suspend fun loadHome(initial: Boolean, force: Boolean = false, silent: Boolean = false) {
        if (!silent) {
            if (!force && !initial && appCache.home != null && recent.isNotEmpty()) {
                refreshing = true
            } else if (initial && recent.isEmpty()) {
                loading = true
            } else if (force) {
                refreshing = true
            }
        }
        error = null
        try {
            coroutineScope {
                val recentDef = async { api.homeRail("queue") }
                val vibeDef = async { api.homeRail("continue_vibe") }
                val plDef = async { api.homeRail("from_playlists") }
                val listsDef = async { api.lists(forHome = true) }
                val tagsDef = async { runCatching { api.tags(onlyUsed = true) }.getOrNull() }
                // Paint Now/Plan as soon as each returns — do not wait for other rails.
                launch {
                    val now = withTimeoutOrNull(12_000) {
                        runCatching { api.homeNow(slot = nowSlot, mood = nowMood, limit = 6) }.getOrNull()
                    }
                    applyNowResponse(now)
                    if (now != null) {
                        runCatching { api.trackSurface("now_impression", surface = "android_home") }
                    }
                }
                launch {
                    val plan = withTimeoutOrNull(12_000) {
                        runCatching { api.homePlan() }.getOrNull()
                    }
                    applyPlanResponse(plan)
                }
                recent = recentDef.await().items.orEmpty()
                vibe = vibeDef.await().items.orEmpty()
                fromPlaylists = plDef.await().items.orEmpty()
                topFolders = listsDef.await().lists.orEmpty()
                    .sortedByDescending { it.count ?: 0 }
                    .take(8)
                tags = usedTags(tagsDef.await()?.tags.orEmpty())
                persistHomeSnapshot()
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
            if (!nowLoaded) nowLoaded = true
            if (!planLoaded) planLoaded = true
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
            nowPicks = nowPicks.filterNot { it.video_id == id }
            nowSuggestions = nowSuggestions.filterNot { it.video_id == id }
        },
        onTag = { tagCard = it },
        onMove = { moveCard = it },
        onInterestDone = { scope.launch { loadHome(initial = false, force = true) } },
        onPlanChanged = { scope.launch { loadHome(initial = false, force = true) } },
        cache = appCache,
    )

    LaunchedEffect(Unit) {
        // Disk cache paints instantly; silent refresh so pull spinner / «Подбираем…» do not flash.
        if (appCache.home != null) {
            loading = false
            loadHome(initial = false, force = true, silent = true)
        } else {
            loadHome(initial = true, force = true)
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

    removeTarget?.let { folder ->
        FolderRemoveDialog(
            folder = folder,
            onDismiss = { removeTarget = null },
            onHideFromHome = {
                val id = folder.id ?: return@FolderRemoveDialog
                scope.launch {
                    val r = runCatching { api.hideListFromHome(id, true) }.getOrNull()
                    if (r?.ok == true) {
                        topFolders = topFolders.filterNot { it.id == id }
                        appCache.invalidateHome()
                        appCache.invalidateFolders()
                        Toast.makeText(context, "Скрыто", Toast.LENGTH_SHORT).show()
                    } else {
                        Toast.makeText(context, r?.error ?: "Ошибка", Toast.LENGTH_SHORT).show()
                    }
                    removeTarget = null
                    folderEdit = false
                }
            },
            onDeleteEverywhere = {
                val id = folder.id ?: return@FolderRemoveDialog
                scope.launch {
                    val r = runCatching { api.deleteList(id) }.getOrNull()
                    if (r?.ok == true) {
                        topFolders = topFolders.filterNot { it.id == id }
                        appCache.invalidateAll()
                        Toast.makeText(context, "Удалено", Toast.LENGTH_SHORT).show()
                    } else {
                        Toast.makeText(context, r?.error ?: "Ошибка", Toast.LENGTH_SHORT).show()
                    }
                    removeTarget = null
                    folderEdit = false
                }
            },
        )
    }

    Box(
        modifier = Modifier.fillMaxSize().background(CqBg),
    ) {
        Column(modifier = Modifier.fillMaxSize()) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp)
                    .padding(top = 14.dp, bottom = 4.dp)
                    .zIndex(50f),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    "Kyro",
                    style = KyroBrandStyle,
                    modifier = Modifier.padding(end = 4.dp),
                )
                if (folderEdit) {
                    Text(
                        "Готово",
                        style = MaterialTheme.typography.titleMedium.copy(
                            fontFamily = KyroFont,
                            fontWeight = FontWeight.Bold,
                            fontSize = 16.sp,
                            color = Color(0xFF0A0A0C),
                        ),
                        modifier = Modifier
                            .clip(RoundedCornerShape(12.dp))
                            .background(Color(0xFFF3F3F5))
                            .clickable {
                                folderEdit = false
                                trashHot = false
                            }
                            .padding(horizontal = 16.dp, vertical = 9.dp),
                    )
                } else {
                    Text(
                        "сегодня",
                        style = MaterialTheme.typography.bodySmall.copy(
                            fontFamily = KyroFont,
                            fontWeight = FontWeight.Normal,
                            fontSize = 11.sp,
                            color = CqMuted,
                        ),
                        modifier = Modifier
                            .clip(RoundedCornerShape(999.dp))
                            .background(CqElev)
                            .clickable(onClick = onOpenToday)
                            .padding(horizontal = 12.dp, vertical = 8.dp),
                    )
                }
            }

            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp)
                    .padding(bottom = 8.dp)
                    .height(48.dp)
                    .clip(RoundedCornerShape(24.dp))
                    .background(CqElev)
                    .border(1.dp, CqBorder, RoundedCornerShape(24.dp))
                    .clickable(onClick = onOpenSearch)
                    .padding(horizontal = 14.dp),
                contentAlignment = Alignment.CenterStart,
            ) {
                Text("⌕  Название, канал, описание…", color = CqMuted, style = MaterialTheme.typography.bodyMedium)
            }

            Box(modifier = Modifier.weight(1f).fillMaxWidth()) {
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
                        modifier = Modifier.fillMaxSize(),
                    ) {
                        LazyColumn(
                            modifier = Modifier.fillMaxSize(),
                            contentPadding = PaddingValues(bottom = 72.dp),
                        ) {
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
                                        Text("Пока пусто", color = CqMuted, modifier = Modifier.padding(horizontal = 12.dp))
                                    } else {
                                        FolderGrid(taggedFolders.take(8), onOpenFolder)
                                    }
                                }
                                item {
                                    SectionLabel("Видео с тегом", Modifier.padding(horizontal = 12.dp))
                                    if (taggedVideos.isEmpty()) {
                                        Text("Пока пусто", color = CqMuted, modifier = Modifier.padding(horizontal = 12.dp))
                                    } else {
                                        VideoSpine(taggedVideos) { c, a -> actions.handle(c, a) }
                                    }
                                }
                            } else {
                                // Hide empty «Сейчас» / plan shells after load — less hierarchy noise.
                                if (!nowLoaded || nowPicks.isNotEmpty() || nowSlots.isNotEmpty() || nowMoods.isNotEmpty()) {
                                    item {
                                        SectionLabel("Сейчас", Modifier.padding(horizontal = 12.dp))
                                        if (nowMeta.isNotBlank()) {
                                            Text(
                                                nowMeta,
                                                color = CqMuted,
                                                style = MaterialTheme.typography.bodySmall,
                                                modifier = Modifier.padding(horizontal = 12.dp).padding(bottom = 6.dp),
                                            )
                                        }
                                        if (nowSlots.isNotEmpty()) {
                                            LazyRow(
                                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                                                contentPadding = PaddingValues(horizontal = 12.dp),
                                            ) {
                                                items(nowSlots, key = { it.id.orEmpty() }) { s ->
                                                    val slotLabel = s.label.orEmpty().ifBlank { "Слот" }
                                                    TagChip(slotLabel, selected = nowSlot == s.id) {
                                                        nowSlot = s.id.orEmpty().ifBlank { "any" }
                                                        scope.launch { loadNow(slot = nowSlot, mood = nowMood) }
                                                    }
                                                }
                                            }
                                            Spacer(modifier = Modifier.height(8.dp))
                                        }
                                        if (nowMoods.isNotEmpty()) {
                                            LazyRow(
                                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                                                contentPadding = PaddingValues(horizontal = 12.dp),
                                            ) {
                                                item {
                                                    TagChip("Все", selected = nowMood.isBlank()) {
                                                        nowMood = ""
                                                        scope.launch { loadNow(slot = nowSlot, mood = "") }
                                                    }
                                                }
                                                items(nowMoods, key = { it.id.orEmpty() }) { m ->
                                                    val moodLabel = m.label.orEmpty().ifBlank { "Настроение" }
                                                    TagChip(moodLabel, selected = nowMood == m.id) {
                                                        nowMood = m.id.orEmpty()
                                                        scope.launch { loadNow(slot = nowSlot, mood = nowMood) }
                                                    }
                                                }
                                            }
                                            Spacer(modifier = Modifier.height(8.dp))
                                        }
                                        if (nowPicks.isEmpty()) {
                                            Text(
                                                if (!nowLoaded) "Подбираем…"
                                                else "Пока нечего предложить — сохраните видео из YouTube",
                                                color = CqMuted,
                                                modifier = Modifier.padding(horizontal = 12.dp, vertical = 4.dp),
                                            )
                                        } else {
                                            VideoRail(nowPicks) { c, a -> actions.handle(c, a) }
                                        }
                                    }
                                }
                                if (nowSuggestions.isNotEmpty()) {
                                    item {
                                        SectionLabel("Можно посмотреть", Modifier.padding(horizontal = 12.dp))
                                        VideoRail(nowSuggestions) { c, a -> actions.handle(c, a) }
                                    }
                                }
                                if (!planLoaded || planTonight.isNotEmpty() || planSuggestTonight.isNotEmpty()) {
                                    item {
                                        SectionLabel("План на вечер", Modifier.padding(horizontal = 12.dp))
                                        if (planTonight.isNotEmpty()) {
                                            VideoRail(planTonight) { c, a -> actions.handle(c, a) }
                                        } else if (planSuggestTonight.isNotEmpty()) {
                                            Text(
                                                "Предложения — нажмите ⋮ → «В план на вечер»",
                                                color = CqMuted,
                                                style = MaterialTheme.typography.bodySmall,
                                                modifier = Modifier.padding(horizontal = 12.dp).padding(bottom = 6.dp),
                                            )
                                            VideoRail(planSuggestTonight) { c, a -> actions.handle(c, a) }
                                        } else {
                                            Text(
                                                if (!planLoaded) "Подбираем…"
                                                else "Сохраните видео — предложим, что добавить в план",
                                                color = CqMuted,
                                                modifier = Modifier.padding(horizontal = 12.dp, vertical = 4.dp),
                                            )
                                        }
                                    }
                                }
                                item {
                                    SectionLabel("Недавно сохранили", Modifier.padding(horizontal = 12.dp))
                                    if (recent.isEmpty()) {
                                        Text(
                                            "Пока пусто — сохраните ролик из YouTube через «Поделиться» → Kyro",
                                            color = CqMuted,
                                            modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                                        )
                                    } else {
                                        VideoSpine(recent.take(12)) { c, a -> actions.handle(c, a) }
                                    }
                                }
                                val recs = if (vibe.isNotEmpty()) vibe else fromPlaylists
                                if (recs.isNotEmpty()) {
                                    item {
                                        SectionLabel("Могут подойти", Modifier.padding(horizontal = 12.dp))
                                        VideoRail(recs) { c, a -> actions.handle(c, a) }
                                    }
                                }
                                item {
                                    Row(
                                        modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp).padding(top = 14.dp, bottom = 8.dp),
                                        horizontalArrangement = Arrangement.SpaceBetween,
                                        verticalAlignment = Alignment.CenterVertically,
                                    ) {
                                        Text("ВАШИ ПАПКИ", style = MaterialTheme.typography.labelSmall, color = CqMuted)
                                        Text("все →", color = CqText, style = MaterialTheme.typography.bodySmall, modifier = Modifier.clickable(onClick = onOpenFolders))
                                    }
                                    if (topFolders.isEmpty()) Text("Папок пока нет", color = CqMuted, modifier = Modifier.padding(horizontal = 12.dp))
                                    else EditableFolderGrid(
                                        folders = topFolders,
                                        editing = folderEdit,
                                        trashBounds = trashBounds,
                                        onOpenFolder = onOpenFolder,
                                        onEnterEdit = { folderEdit = true },
                                        onDragHotChange = { trashHot = it },
                                        onDropOnTrash = { removeTarget = it },
                                        onReorder = { next ->
                                            topFolders = next
                                            scope.launch {
                                                val ids = next.mapNotNull { it.id }
                                                runCatching { api.reorderLists(ids) }
                                                appCache.invalidateHome()
                                                appCache.invalidateFolders()
                                            }
                                        },
                                    )
                                    Spacer(Modifier.height(12.dp))
                                }
                            }
                        }
                    }
                }
            }
            BottomBar(0, onHome = {}, onFolders = onOpenFolders, onProfile = onOpenProfile)
        }

        FolderTrashZone(
            editing = folderEdit,
            hot = trashHot,
            onBounds = { trashBounds = it },
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .padding(bottom = 72.dp)
                .zIndex(40f),
        )
    }
}
