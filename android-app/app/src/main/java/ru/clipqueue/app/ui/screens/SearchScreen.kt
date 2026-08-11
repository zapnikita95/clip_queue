package ru.clipqueue.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import ru.clipqueue.app.ApiClient
import ru.clipqueue.app.data.VideoCard
import ru.clipqueue.app.ui.components.SearchBarWithMic
import ru.clipqueue.app.ui.components.SectionLabel
import ru.clipqueue.app.ui.components.VideoSpine
import ru.clipqueue.app.ui.rememberVideoActions
import ru.clipqueue.app.ui.theme.CqAccent
import ru.clipqueue.app.ui.theme.CqBg
import ru.clipqueue.app.ui.theme.CqElev
import ru.clipqueue.app.ui.theme.CqMuted
import ru.clipqueue.app.ui.theme.CqText
import ru.clipqueue.app.ui.theme.KyroFont

@Composable
fun SearchScreen(
    api: ApiClient,
    onBack: () -> Unit,
    onOpenVideo: (String) -> Unit,
    initialQuery: String = "",
) {
    var query by remember { mutableStateOf(initialQuery) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var items by remember { mutableStateOf<List<VideoCard>>(emptyList()) }
    var meta by remember { mutableStateOf("") }
    val scope = rememberCoroutineScope()
    var debounce by remember { mutableStateOf<Job?>(null) }

    val actions = rememberVideoActions(
        api = api,
        onOpenVideo = onOpenVideo,
        onRemoved = { id -> items = items.filterNot { it.video_id == id } },
    )

    fun runSearch(q: String) {
        debounce?.cancel()
        debounce = scope.launch {
            delay(280)
            val trimmed = q.trim()
            if (trimmed.length < 2) {
                items = emptyList()
                meta = ""
                error = null
                loading = false
                return@launch
            }
            loading = true
            error = null
            try {
                val r = api.search(trimmed, limit = 40)
                items = r.items.orEmpty()
                meta = if (items.isEmpty()) "Ничего не нашлось" else "${items.size} в библиотеке"
            } catch (e: Exception) {
                error = e.message ?: "Ошибка поиска"
                items = emptyList()
            } finally {
                loading = false
            }
        }
    }

    LaunchedEffect(initialQuery) {
        if (initialQuery.isNotBlank()) runSearch(initialQuery)
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(CqBg)
            .padding(horizontal = 16.dp)
            .padding(top = 14.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                "Поиск",
                style = MaterialTheme.typography.titleLarge.copy(
                    fontFamily = KyroFont,
                    fontWeight = FontWeight.SemiBold,
                    color = CqText,
                ),
            )
            Text(
                "Закрыть",
                color = CqMuted,
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier
                    .clip(RoundedCornerShape(10.dp))
                    .background(CqElev)
                    .clickable(onClick = onBack)
                    .padding(horizontal = 12.dp, vertical = 8.dp),
            )
        }
        Box(modifier = Modifier.height(12.dp)) {}
        SearchBarWithMic(
            value = query,
            onValueChange = {
                query = it
                runSearch(it)
            },
            placeholder = "Название, канал, описание…",
        )
        if (meta.isNotBlank()) {
            Text(
                meta,
                color = CqMuted,
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(top = 10.dp),
            )
        }
        Box(modifier = Modifier.height(8.dp)) {}
        when {
            loading && items.isEmpty() -> {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center,
                ) {
                    CircularProgressIndicator(color = CqAccent)
                }
            }
            error != null && items.isEmpty() -> {
                Text(error.orEmpty(), color = CqAccent)
            }
            query.trim().length < 2 -> {
                Text(
                    "Введите хотя бы 2 символа",
                    color = CqMuted,
                    modifier = Modifier.padding(top = 20.dp),
                )
            }
            items.isEmpty() -> {
                Text(
                    "Ничего не нашлось",
                    color = CqMuted,
                    modifier = Modifier.padding(top = 20.dp),
                )
            }
            else -> {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(bottom = 24.dp),
                ) {
                    item { SectionLabel("В библиотеке") }
                    item {
                        VideoSpine(items) { c, a -> actions.handle(c, a) }
                    }
                }
            }
        }
    }
}
