package ru.clipqueue.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.RemoveRedEye
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import ru.clipqueue.app.data.ListCard
import ru.clipqueue.app.data.VideoCard
import ru.clipqueue.app.ui.theme.CqAccent
import ru.clipqueue.app.ui.theme.CqBorder
import ru.clipqueue.app.ui.theme.CqElev
import ru.clipqueue.app.ui.theme.CqElev2
import ru.clipqueue.app.ui.theme.CqMuted
import ru.clipqueue.app.ui.theme.CqText

enum class CardAction {
    Open,
    Watched,
    InterestHot,
    InterestOk,
    InterestLow,
    Dismiss,
}

@Composable
fun SectionLabel(text: String) {
    Text(
        text = text.uppercase(),
        style = MaterialTheme.typography.labelSmall,
        modifier = Modifier.padding(top = 18.dp, bottom = 10.dp),
    )
}

@Composable
fun FilterChip(
    label: String,
    selected: Boolean,
    onClick: () -> Unit,
) {
    Text(
        text = label,
        color = if (selected) CqText else CqMuted,
        style = MaterialTheme.typography.bodySmall,
        modifier = Modifier
            .clip(RoundedCornerShape(20.dp))
            .background(if (selected) CqAccent.copy(alpha = 0.35f) else CqElev)
            .border(1.dp, if (selected) CqAccent else CqBorder, RoundedCornerShape(20.dp))
            .clickable(onClick = onClick)
            .padding(horizontal = 12.dp, vertical = 8.dp),
    )
}

@Composable
fun VideoRail(
    items: List<VideoCard>,
    onAction: (VideoCard, CardAction) -> Unit,
) {
    LazyRow(
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        contentPadding = PaddingValues(end = 8.dp),
    ) {
        items(items, key = { it.video_id ?: it.title.orEmpty() }) { card ->
            VideoThumbCard(card, onAction)
        }
    }
}

@Composable
fun VideoThumbCard(
    card: VideoCard,
    onAction: (VideoCard, CardAction) -> Unit,
) {
    var menu by remember { mutableStateOf(false) }
    Column(modifier = Modifier.width(156.dp)) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .aspectRatio(16f / 10f)
                .clip(RoundedCornerShape(10.dp))
                .background(Brush.linearGradient(listOf(CqElev2, CqElev)))
                .clickable { onAction(card, CardAction.Open) },
        ) {
            if (!card.thumb_url.isNullOrBlank()) {
                AsyncImage(
                    model = card.thumb_url,
                    contentDescription = card.title,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier.fillMaxSize(),
                )
            }
            IconButton(
                onClick = { onAction(card, CardAction.Watched) },
                modifier = Modifier
                    .align(Alignment.TopStart)
                    .padding(2.dp)
                    .size(36.dp)
                    .background(CqElev.copy(alpha = 0.72f), CircleShape),
            ) {
                Icon(
                    Icons.Default.RemoveRedEye,
                    contentDescription = "Просмотрено",
                    tint = CqText,
                    modifier = Modifier.size(18.dp),
                )
            }
            Box(modifier = Modifier.align(Alignment.TopEnd)) {
                IconButton(
                    onClick = { menu = true },
                    modifier = Modifier
                        .padding(2.dp)
                        .size(36.dp)
                        .background(CqElev.copy(alpha = 0.72f), CircleShape),
                ) {
                    Icon(
                        Icons.Default.MoreVert,
                        contentDescription = "Ещё",
                        tint = CqText,
                        modifier = Modifier.size(18.dp),
                    )
                }
                DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                    DropdownMenuItem(
                        text = { Text("Очень интересно") },
                        onClick = { menu = false; onAction(card, CardAction.InterestHot) },
                    )
                    DropdownMenuItem(
                        text = { Text("Интересно") },
                        onClick = { menu = false; onAction(card, CardAction.InterestOk) },
                    )
                    DropdownMenuItem(
                        text = { Text("Менее интересно") },
                        onClick = { menu = false; onAction(card, CardAction.InterestLow) },
                    )
                    DropdownMenuItem(
                        text = { Text("Просмотрено") },
                        onClick = { menu = false; onAction(card, CardAction.Watched) },
                    )
                    DropdownMenuItem(
                        text = { Text("Удалить") },
                        onClick = { menu = false; onAction(card, CardAction.Dismiss) },
                    )
                }
            }
            val dur = card.duration_label ?: formatDuration(card.duration_sec)
            if (!dur.isNullOrBlank()) {
                Text(
                    text = dur,
                    color = CqText,
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier
                        .align(Alignment.BottomEnd)
                        .padding(6.dp)
                        .clip(RoundedCornerShape(4.dp))
                        .background(CqElev.copy(alpha = 0.85f))
                        .padding(horizontal = 5.dp, vertical = 2.dp),
                )
            }
        }
        Spacer(Modifier.height(6.dp))
        Text(
            text = card.title.orEmpty().ifBlank { "Без названия" },
            style = MaterialTheme.typography.titleMedium,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
            color = CqText,
            modifier = Modifier.clickable { onAction(card, CardAction.Open) },
        )
        Text(
            text = card.channel_title.orEmpty(),
            style = MaterialTheme.typography.bodySmall,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            color = CqMuted,
        )
    }
}

@Composable
fun VideoListRow(
    card: VideoCard,
    onAction: (VideoCard, CardAction) -> Unit,
) {
    var menu by remember { mutableStateOf(false) }
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onAction(card, CardAction.Open) }
            .padding(vertical = 10.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            modifier = Modifier
                .width(96.dp)
                .aspectRatio(16f / 10f)
                .clip(RoundedCornerShape(8.dp))
                .background(CqElev2),
        ) {
            if (!card.thumb_url.isNullOrBlank()) {
                AsyncImage(
                    model = card.thumb_url,
                    contentDescription = null,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier.fillMaxSize(),
                )
            }
            IconButton(
                onClick = { onAction(card, CardAction.Watched) },
                modifier = Modifier
                    .align(Alignment.TopStart)
                    .size(32.dp)
                    .background(CqElev.copy(alpha = 0.7f), CircleShape),
            ) {
                Icon(Icons.Default.RemoveRedEye, null, tint = CqText, modifier = Modifier.size(16.dp))
            }
        }
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = card.title.orEmpty(),
                style = MaterialTheme.typography.titleMedium,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                text = listOfNotNull(
                    card.channel_title?.takeIf { it.isNotBlank() },
                    card.duration_label ?: formatDuration(card.duration_sec),
                    card.status?.takeIf { it.isNotBlank() },
                ).joinToString(" · "),
                style = MaterialTheme.typography.bodySmall,
                color = CqMuted,
            )
        }
        Box {
            IconButton(onClick = { menu = true }) {
                Icon(Icons.Default.MoreVert, contentDescription = "Ещё", tint = CqMuted)
            }
            DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                DropdownMenuItem(text = { Text("Просмотрено") }, onClick = { menu = false; onAction(card, CardAction.Watched) })
                DropdownMenuItem(text = { Text("Очень интересно") }, onClick = { menu = false; onAction(card, CardAction.InterestHot) })
                DropdownMenuItem(text = { Text("Удалить") }, onClick = { menu = false; onAction(card, CardAction.Dismiss) })
            }
        }
    }
}

@Composable
fun FolderCarousel(
    folders: List<ListCard>,
    onOpenFolder: (ListCard) -> Unit,
    onOpenAll: () -> Unit = {},
) {
    LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        items(folders, key = { it.id ?: 0 }) { folder ->
            Column(
                modifier = Modifier
                    .width(148.dp)
                    .clip(RoundedCornerShape(14.dp))
                    .background(CqElev)
                    .border(1.dp, CqBorder, RoundedCornerShape(14.dp))
                    .clickable { onOpenFolder(folder) }
                    .padding(10.dp),
            ) {
                Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    val covers = folder.covers.orEmpty().take(3)
                    if (covers.isEmpty()) {
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(64.dp)
                                .clip(RoundedCornerShape(8.dp))
                                .background(CqElev2),
                            contentAlignment = Alignment.Center,
                        ) {
                            Icon(Icons.Default.Folder, null, tint = CqMuted)
                        }
                    } else {
                        covers.forEach { c ->
                            AsyncImage(
                                model = c.thumb_url,
                                contentDescription = null,
                                contentScale = ContentScale.Crop,
                                modifier = Modifier
                                    .weight(1f)
                                    .height(64.dp)
                                    .clip(RoundedCornerShape(6.dp)),
                            )
                        }
                    }
                }
                Spacer(Modifier.height(8.dp))
                Text(
                    folder.title.orEmpty(),
                    style = MaterialTheme.typography.titleMedium,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                Text("${folder.count ?: 0} видео", color = CqMuted, style = MaterialTheme.typography.bodySmall)
            }
        }
        item {
            Column(
                modifier = Modifier
                    .width(110.dp)
                    .height(120.dp)
                    .clip(RoundedCornerShape(14.dp))
                    .background(CqElev)
                    .border(1.dp, CqBorder, RoundedCornerShape(14.dp))
                    .clickable(onClick = onOpenAll)
                    .padding(12.dp),
                verticalArrangement = Arrangement.Center,
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Text("Все →", color = CqAccent, style = MaterialTheme.typography.titleMedium)
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
            .background(CqElev)
            .border(width = 1.dp, color = CqBorder, shape = RoundedCornerShape(0))
            .padding(top = 12.dp, bottom = 14.dp),
        horizontalArrangement = Arrangement.SpaceEvenly,
    ) {
        BottomTab(0, selected, "Лента", Icons.Default.Home, onHome)
        BottomTab(1, selected, "Папки", Icons.Default.Folder, onFolders)
        BottomTab(2, selected, "Ещё", Icons.Default.Person, onProfile)
    }
}

@Composable
private fun BottomTab(
    index: Int,
    selected: Int,
    label: String,
    icon: ImageVector,
    onClick: () -> Unit,
) {
    val on = selected == index
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier
            .clip(RoundedCornerShape(16.dp))
            .clickable(onClick = onClick)
            .padding(horizontal = 22.dp, vertical = 8.dp),
    ) {
        Icon(
            icon,
            contentDescription = label,
            tint = if (on) CqAccent else CqMuted,
            modifier = Modifier.size(32.dp),
        )
        Spacer(Modifier.height(6.dp))
        Text(
            label,
            color = if (on) CqAccent else CqMuted,
            fontSize = 13.sp,
            style = MaterialTheme.typography.labelSmall,
        )
    }
}

fun formatDuration(sec: Int?): String? {
    if (sec == null || sec <= 0) return null
    val h = sec / 3600
    val m = (sec % 3600) / 60
    val s = sec % 60
    return if (h > 0) "%d:%02d:%02d".format(h, m, s) else "%d:%02d".format(m, s)
}
