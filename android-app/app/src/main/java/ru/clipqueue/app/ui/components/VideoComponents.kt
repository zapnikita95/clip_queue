package ru.clipqueue.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxHeight
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
import androidx.compose.ui.platform.LocalConfiguration
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
    Tag,
    Move,
}

@Composable
fun SectionLabel(text: String, modifier: Modifier = Modifier) {
    Text(
        text = text.uppercase(),
        style = MaterialTheme.typography.labelSmall,
        color = CqMuted,
        modifier = modifier.padding(top = 14.dp, bottom = 8.dp),
    )
}

@Composable
fun ToolIconButton(
    label: String,
    selected: Boolean,
    onClick: () -> Unit,
    icon: @Composable () -> Unit,
) {
    Row(
        modifier = Modifier
            .clip(RoundedCornerShape(20.dp))
            .background(if (selected) CqAccent.copy(alpha = 0.35f) else CqElev)
            .border(1.dp, if (selected) CqAccent else CqBorder, RoundedCornerShape(20.dp))
            .clickable(onClick = onClick)
            .padding(horizontal = 12.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        icon()
        Text(label, color = if (selected) CqText else CqMuted, style = MaterialTheme.typography.bodySmall)
    }
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
            .padding(horizontal = 12.dp, vertical = 7.dp),
    )
}

@Composable
fun TagChip(label: String, selected: Boolean = false, onClick: (() -> Unit)? = null) {
    val mod = Modifier
        .clip(RoundedCornerShape(999.dp))
        .background(if (selected) CqAccent.copy(alpha = 0.4f) else CqElev2)
        .border(1.dp, if (selected) CqAccent else CqBorder, RoundedCornerShape(999.dp))
        .then(if (onClick != null) Modifier.clickable(onClick = onClick) else Modifier)
        .padding(horizontal = 10.dp, vertical = 6.dp)
    Text(label, color = if (selected) CqText else CqMuted, style = MaterialTheme.typography.bodySmall, modifier = mod)
}

@Composable
private fun ThumbOverlayButton(
    modifier: Modifier,
    onClick: () -> Unit,
    content: @Composable () -> Unit,
) {
    Box(
        modifier = modifier
            .size(22.dp)
            .clip(CircleShape)
            .background(CqElev.copy(alpha = 0.55f))
            .clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) { content() }
}

@Composable
fun VideoRail(
    items: List<VideoCard>,
    onAction: (VideoCard, CardAction) -> Unit,
) {
    val screenW = LocalConfiguration.current.screenWidthDp
    val cardW = (screenW * 0.72f).coerceIn(200f, 280f).dp
    LazyRow(
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        contentPadding = PaddingValues(horizontal = 12.dp),
        modifier = Modifier.fillMaxWidth(),
    ) {
        items(items, key = { it.video_id ?: it.title.orEmpty() }) { card ->
            VideoThumbCard(card, onAction, width = cardW)
        }
    }
}

@Composable
fun VideoThumbCard(
    card: VideoCard,
    onAction: (VideoCard, CardAction) -> Unit,
    width: androidx.compose.ui.unit.Dp = 200.dp,
) {
    var menu by remember { mutableStateOf(false) }
    Column(modifier = Modifier.width(width)) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .aspectRatio(16f / 9f)
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
            ThumbOverlayButton(
                modifier = Modifier.align(Alignment.TopStart).padding(6.dp),
                onClick = { onAction(card, CardAction.Watched) },
            ) {
                Icon(Icons.Default.RemoveRedEye, "Просмотрено", tint = CqText, modifier = Modifier.size(13.dp))
            }
            Box(modifier = Modifier.align(Alignment.TopEnd).padding(6.dp)) {
                ThumbOverlayButton(modifier = Modifier, onClick = { menu = true }) {
                    Icon(Icons.Default.MoreVert, "Ещё", tint = CqText, modifier = Modifier.size(13.dp))
                }
                DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                    DropdownMenuItem(text = { Text("Очень интересно") }, onClick = { menu = false; onAction(card, CardAction.InterestHot) })
                    DropdownMenuItem(text = { Text("Интересно") }, onClick = { menu = false; onAction(card, CardAction.InterestOk) })
                    DropdownMenuItem(text = { Text("Менее интересно") }, onClick = { menu = false; onAction(card, CardAction.InterestLow) })
                    DropdownMenuItem(text = { Text("Просмотрено") }, onClick = { menu = false; onAction(card, CardAction.Watched) })
                    DropdownMenuItem(text = { Text("Тег") }, onClick = { menu = false; onAction(card, CardAction.Tag) })
                    DropdownMenuItem(text = { Text("Перенести") }, onClick = { menu = false; onAction(card, CardAction.Move) })
                    DropdownMenuItem(text = { Text("Удалить") }, onClick = { menu = false; onAction(card, CardAction.Dismiss) })
                }
            }
            val dur = card.duration_label ?: formatDuration(card.duration_sec)
            if (!dur.isNullOrBlank()) {
                Text(
                    text = dur,
                    color = CqText,
                    fontSize = 11.sp,
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
    VideoSpineItem(card = card, onAction = onAction)
}

/** Vertical Kyro queue: luminous spine + thumbnail rows. */
@Composable
fun VideoSpine(
    items: List<VideoCard>,
    modifier: Modifier = Modifier,
    onAction: (VideoCard, CardAction) -> Unit,
) {
    Column(
        modifier = modifier.fillMaxWidth().padding(horizontal = 4.dp),
        verticalArrangement = Arrangement.spacedBy(0.dp),
    ) {
        items.forEach { card ->
            VideoSpineItem(card = card, onAction = onAction)
        }
    }
}

@Composable
fun VideoSpineItem(
    card: VideoCard,
    onAction: (VideoCard, CardAction) -> Unit,
) {
    var menu by remember { mutableStateOf(false) }
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 8.dp, vertical = 5.dp),
    ) {
        Box(
            modifier = Modifier
                .align(Alignment.CenterStart)
                .padding(start = 10.dp)
                .width(1.dp)
                .fillMaxHeight()
                .background(CqText.copy(alpha = 0.18f)),
        )
        Box(
            modifier = Modifier
                .align(Alignment.CenterStart)
                .padding(start = 7.dp)
                .size(7.dp)
                .clip(CircleShape)
                .background(CqText.copy(alpha = 0.45f)),
        )
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(start = 28.dp)
                .clip(RoundedCornerShape(14.dp))
                .background(CqElev.copy(alpha = 0.55f))
                .border(1.dp, CqBorder, RoundedCornerShape(14.dp))
                .clickable { onAction(card, CardAction.Open) }
                .padding(8.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                modifier = Modifier
                    .width(120.dp)
                    .aspectRatio(16f / 9f)
                    .clip(RoundedCornerShape(10.dp))
                    .background(CqElev2),
            ) {
                if (!card.thumb_url.isNullOrBlank()) {
                    AsyncImage(
                        model = card.thumb_url,
                        contentDescription = card.title,
                        contentScale = ContentScale.Crop,
                        modifier = Modifier.fillMaxSize(),
                    )
                }
                ThumbOverlayButton(
                    modifier = Modifier.align(Alignment.TopStart).padding(4.dp),
                    onClick = { onAction(card, CardAction.Watched) },
                ) {
                    Icon(Icons.Default.RemoveRedEye, null, tint = CqText, modifier = Modifier.size(12.dp))
                }
                val dur = card.duration_label ?: formatDuration(card.duration_sec)
                if (!dur.isNullOrBlank()) {
                    Text(
                        text = dur,
                        color = CqText,
                        fontSize = 10.sp,
                        modifier = Modifier
                            .align(Alignment.BottomEnd)
                            .padding(4.dp)
                            .clip(RoundedCornerShape(4.dp))
                            .background(CqElev.copy(alpha = 0.85f))
                            .padding(horizontal = 4.dp, vertical = 1.dp),
                    )
                }
            }
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    card.title.orEmpty().ifBlank { "Без названия" },
                    style = MaterialTheme.typography.titleMedium,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                    color = CqText,
                )
                Text(
                    listOfNotNull(
                        card.channel_title?.takeIf { it.isNotBlank() },
                        card.status?.takeIf { it.isNotBlank() }?.let { statusShort(it) },
                    ).joinToString(" · "),
                    style = MaterialTheme.typography.bodySmall,
                    color = CqMuted,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            Box {
                ThumbOverlayButton(modifier = Modifier, onClick = { menu = true }) {
                    Icon(Icons.Default.MoreVert, "Ещё", tint = CqMuted, modifier = Modifier.size(14.dp))
                }
                DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                    DropdownMenuItem(text = { Text("Просмотрено") }, onClick = { menu = false; onAction(card, CardAction.Watched) })
                    DropdownMenuItem(text = { Text("Очень интересно") }, onClick = { menu = false; onAction(card, CardAction.InterestHot) })
                    DropdownMenuItem(text = { Text("Тег") }, onClick = { menu = false; onAction(card, CardAction.Tag) })
                    DropdownMenuItem(text = { Text("Перенести") }, onClick = { menu = false; onAction(card, CardAction.Move) })
                    DropdownMenuItem(text = { Text("Удалить") }, onClick = { menu = false; onAction(card, CardAction.Dismiss) })
                }
            }
        }
    }
}

private fun statusShort(status: String): String? = when (status) {
    "watched" -> "смотрели"
    "in_progress" -> "начато"
    "archived" -> "архив"
    "queue" -> "в очереди"
    else -> null
}

@Composable
fun FolderGrid(
    folders: List<ListCard>,
    onOpenFolder: (ListCard) -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier.fillMaxWidth().padding(horizontal = 12.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        folders.chunked(2).forEach { row ->
            Row(
                horizontalArrangement = Arrangement.spacedBy(10.dp),
                modifier = Modifier.fillMaxWidth().height(IntrinsicSize.Min),
            ) {
                row.forEach { folder ->
                    FolderGridCell(folder, onOpenFolder, Modifier.weight(1f).fillMaxHeight())
                }
                if (row.size == 1) Spacer(Modifier.weight(1f))
            }
        }
    }
}

@Composable
private fun FolderGridCell(
    folder: ListCard,
    onOpenFolder: (ListCard) -> Unit,
    modifier: Modifier,
) {
    Column(
        modifier = modifier
            .clip(RoundedCornerShape(14.dp))
            .background(CqElev)
            .border(1.dp, CqBorder, RoundedCornerShape(14.dp))
            .clickable { onOpenFolder(folder) }
            .padding(10.dp),
    ) {
        Row(horizontalArrangement = Arrangement.spacedBy(3.dp), modifier = Modifier.fillMaxWidth()) {
            val covers = folder.covers.orEmpty().take(3)
            if (covers.isEmpty()) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(56.dp)
                        .clip(RoundedCornerShape(8.dp))
                        .background(CqElev2),
                    contentAlignment = Alignment.Center,
                ) { Icon(Icons.Default.Folder, null, tint = CqMuted, modifier = Modifier.size(22.dp)) }
            } else {
                covers.forEach { c ->
                    AsyncImage(
                        model = c.thumb_url,
                        contentDescription = null,
                        contentScale = ContentScale.Crop,
                        modifier = Modifier.weight(1f).height(56.dp).clip(RoundedCornerShape(6.dp)),
                    )
                }
            }
        }
        Spacer(Modifier.height(8.dp))
        Text(
            folder.title.orEmpty(),
            style = MaterialTheme.typography.titleMedium,
            maxLines = 2,
            minLines = 2,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.height(44.dp),
        )
        Text("${folder.count ?: 0} видео", color = CqMuted, style = MaterialTheme.typography.bodySmall)
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
            .padding(horizontal = 4.dp, vertical = 6.dp),
        horizontalArrangement = Arrangement.SpaceEvenly,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        BottomTab(0, selected, "Очередь", Icons.Default.Home, onHome, Modifier.weight(1f))
        BottomTab(1, selected, "Папки", Icons.Default.Folder, onFolders, Modifier.weight(1f))
        BottomTab(2, selected, "Профиль", Icons.Default.Person, onProfile, Modifier.weight(1f))
    }
}

@Composable
private fun BottomTab(
    index: Int,
    selected: Int,
    label: String,
    icon: ImageVector,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val on = selected == index
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
        modifier = modifier
            .clip(RoundedCornerShape(12.dp))
            .background(if (on) CqAccent.copy(alpha = 0.12f) else androidx.compose.ui.graphics.Color.Transparent)
            .clickable(onClick = onClick)
            .padding(vertical = 8.dp),
    ) {
        Icon(icon, label, tint = if (on) CqText else CqMuted, modifier = Modifier.size(26.dp))
        Spacer(Modifier.height(2.dp))
        Text(label, color = if (on) CqText else CqMuted, fontSize = 12.sp)
    }
}

fun formatDuration(sec: Int?): String? {
    if (sec == null || sec <= 0) return null
    val h = sec / 3600
    val m = (sec % 3600) / 60
    val s = sec % 60
    return if (h > 0) "%d:%02d:%02d".format(h, m, s) else "%d:%02d".format(m, s)
}
