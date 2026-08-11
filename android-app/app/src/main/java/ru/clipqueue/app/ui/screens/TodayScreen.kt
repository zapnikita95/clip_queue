package ru.clipqueue.app.ui.screens

import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import kotlinx.coroutines.launch
import ru.clipqueue.app.ApiClient
import ru.clipqueue.app.data.VideoCard
import ru.clipqueue.app.ui.theme.CqAccent
import ru.clipqueue.app.ui.theme.CqBg
import ru.clipqueue.app.ui.theme.CqElev
import ru.clipqueue.app.ui.theme.CqMuted
import ru.clipqueue.app.ui.theme.CqText
import ru.clipqueue.app.ui.theme.KyroFont
import kotlin.math.roundToInt

@Composable
fun TodayScreen(
    api: ApiClient,
    onBack: () -> Unit,
    onOpenVideo: (String) -> Unit,
) {
    var loading by remember { mutableStateOf(true) }
    var meta by remember { mutableStateOf("") }
    var now by remember { mutableStateOf<List<VideoCard>>(emptyList()) }
    var evening by remember { mutableStateOf<List<VideoCard>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current

    suspend fun load() {
        loading = true
        error = null
        try {
            val r = api.homeToday(limit = 8)
            now = r.now.orEmpty()
            evening = r.evening.orEmpty()
            meta = listOfNotNull(
                r.daypart_label?.takeIf { it.isNotBlank() },
                r.slot_label?.takeIf { it.isNotBlank() },
            ).joinToString(" · ")
        } catch (e: Exception) {
            error = e.message ?: "Не удалось загрузить"
        } finally {
            loading = false
        }
    }

    LaunchedEffect(Unit) { load() }

    fun hide(videoId: String) {
        scope.launch {
            runCatching { api.hideFromToday(videoId) }
            now = now.filterNot { it.video_id == videoId }
            evening = evening.filterNot { it.video_id == videoId }
            Toast.makeText(context, "Скрыто на сегодня", Toast.LENGTH_SHORT).show()
        }
    }

    fun addTonight(videoId: String) {
        scope.launch {
            val r = runCatching { api.addTodayToEvening(videoId) }.getOrNull()
            if (r?.ok == true) {
                Toast.makeText(context, "В плане на вечер", Toast.LENGTH_SHORT).show()
                load()
            } else {
                Toast.makeText(context, r?.error ?: "Ошибка", Toast.LENGTH_SHORT).show()
            }
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(CqBg),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp)
                .padding(top = 14.dp, bottom = 8.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    "Сегодня",
                    style = MaterialTheme.typography.titleLarge.copy(
                        fontFamily = KyroFont,
                        fontWeight = FontWeight.SemiBold,
                        color = CqText,
                    ),
                )
                if (meta.isNotBlank()) {
                    Text(meta, color = CqMuted, style = MaterialTheme.typography.bodySmall)
                }
            }
            Text(
                "Назад",
                color = CqMuted,
                modifier = Modifier
                    .clip(RoundedCornerShape(10.dp))
                    .background(CqElev)
                    .clickable(onClick = onBack)
                    .padding(horizontal = 12.dp, vertical = 8.dp),
            )
        }

        when {
            loading && now.isEmpty() && evening.isEmpty() -> {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center,
                ) {
                    CircularProgressIndicator(color = CqAccent)
                }
            }
            error != null && now.isEmpty() -> {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(error.orEmpty(), color = CqAccent)
                }
            }
            else -> {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(start = 16.dp, end = 16.dp, bottom = 32.dp),
                ) {
                    item {
                        Text(
                            "Сейчас",
                            style = MaterialTheme.typography.titleMedium.copy(fontFamily = KyroFont),
                            color = CqText,
                            modifier = Modifier.padding(top = 8.dp, bottom = 4.dp),
                        )
                        Text(
                            "Смахните влево, чтобы убрать · «В вечер» — в план",
                            color = CqMuted,
                            style = MaterialTheme.typography.bodySmall,
                            modifier = Modifier.padding(bottom = 10.dp),
                        )
                    }
                    if (now.isEmpty()) {
                        item { Text("Пока нечего предложить", color = CqMuted) }
                    } else {
                        items(now, key = { it.video_id.orEmpty() }) { card ->
                            SwipeTodayCard(
                                card = card,
                                showAdd = true,
                                onOpen = { card.video_id?.let(onOpenVideo) },
                                onHide = { card.video_id?.let(::hide) },
                                onAdd = { card.video_id?.let(::addTonight) },
                            )
                            Box(modifier = Modifier.height(10.dp)) {}
                        }
                    }
                    item {
                        Text(
                            "На вечер",
                            style = MaterialTheme.typography.titleMedium.copy(fontFamily = KyroFont),
                            color = CqText,
                            modifier = Modifier.padding(top = 18.dp, bottom = 4.dp),
                        )
                        Text(
                            "План и предложения",
                            color = CqMuted,
                            style = MaterialTheme.typography.bodySmall,
                            modifier = Modifier.padding(bottom = 10.dp),
                        )
                    }
                    if (evening.isEmpty()) {
                        item { Text("Добавьте ролики кнопкой «В вечер»", color = CqMuted) }
                    } else {
                        items(evening, key = { "e-" + it.video_id.orEmpty() }) { card ->
                            SwipeTodayCard(
                                card = card,
                                showAdd = false,
                                onOpen = { card.video_id?.let(onOpenVideo) },
                                onHide = { card.video_id?.let(::hide) },
                                onAdd = {},
                            )
                            Box(modifier = Modifier.height(10.dp)) {}
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun SwipeTodayCard(
    card: VideoCard,
    showAdd: Boolean,
    onOpen: () -> Unit,
    onHide: () -> Unit,
    onAdd: () -> Unit,
) {
    var offsetX by remember { mutableFloatStateOf(0f) }
    val density = LocalDensity.current
    val threshold = with(density) { 96.dp.toPx() }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .offset { IntOffset(offsetX.roundToInt(), 0) }
            .clip(RoundedCornerShape(16.dp))
            .background(CqElev)
            .pointerInput(card.video_id) {
                detectHorizontalDragGestures(
                    onDragEnd = {
                        if (offsetX < -threshold) onHide()
                        offsetX = 0f
                    },
                    onHorizontalDrag = { _, drag ->
                        offsetX = (offsetX + drag).coerceAtMost(0f)
                    },
                )
            }
            .padding(10.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        AsyncImage(
            model = card.thumb_url,
            contentDescription = null,
            contentScale = ContentScale.Crop,
            modifier = Modifier
                .width(112.dp)
                .height(64.dp)
                .clip(RoundedCornerShape(10.dp))
                .clickable(onClick = onOpen),
        )
        Column(
            modifier = Modifier
                .weight(1f)
                .clickable(onClick = onOpen),
        ) {
            if (!card.reason.isNullOrBlank()) {
                Text(
                    card.reason.orEmpty(),
                    color = CqMuted,
                    fontSize = 11.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            Text(
                card.title.orEmpty(),
                color = CqText,
                fontWeight = FontWeight.Medium,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                listOfNotNull(card.channel_title, card.duration_label).joinToString(" · "),
                color = CqMuted,
                fontSize = 12.sp,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
        Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(
                "Скрыть",
                color = CqMuted,
                fontSize = 12.sp,
                modifier = Modifier
                    .clip(RoundedCornerShape(8.dp))
                    .clickable(onClick = onHide)
                    .padding(horizontal = 8.dp, vertical = 6.dp),
            )
            if (showAdd) {
                Text(
                    "В вечер",
                    color = CqText,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier
                        .clip(RoundedCornerShape(8.dp))
                        .background(CqAccent.copy(alpha = 0.15f))
                        .clickable(onClick = onAdd)
                        .padding(horizontal = 8.dp, vertical = 6.dp),
                )
            }
        }
    }
}
