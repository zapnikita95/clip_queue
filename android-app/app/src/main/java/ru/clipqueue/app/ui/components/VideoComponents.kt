package ru.clipqueue.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import ru.clipqueue.app.data.VideoCard
import ru.clipqueue.app.ui.theme.CqElev
import ru.clipqueue.app.ui.theme.CqElev2
import ru.clipqueue.app.ui.theme.CqMuted
import ru.clipqueue.app.ui.theme.CqText

@Composable
fun SectionLabel(text: String) {
    Text(
        text = text.uppercase(),
        style = androidx.compose.material3.MaterialTheme.typography.labelSmall,
        modifier = Modifier.padding(top = 18.dp, bottom = 10.dp),
    )
}

@Composable
fun VideoRail(
    items: List<VideoCard>,
    onOpen: (VideoCard) -> Unit,
) {
    LazyRow(
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        contentPadding = PaddingValues(end = 8.dp),
    ) {
        items(items, key = { it.video_id ?: it.title.orEmpty() }) { card ->
            VideoThumbCard(card, onOpen)
        }
    }
}

@Composable
fun VideoThumbCard(
    card: VideoCard,
    onOpen: (VideoCard) -> Unit,
) {
    Column(
        modifier = Modifier
            .width(148.dp)
            .clickable { onOpen(card) },
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .aspectRatio(16f / 10f)
                .clip(RoundedCornerShape(10.dp))
                .background(
                    Brush.linearGradient(listOf(CqElev2, CqElev)),
                ),
        ) {
            if (!card.thumb_url.isNullOrBlank()) {
                AsyncImage(
                    model = card.thumb_url,
                    contentDescription = card.title,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier.matchParentSize(),
                )
            }
            val dur = formatDuration(card.duration_sec)
            if (dur != null) {
                Text(
                    text = dur,
                    color = CqText,
                    style = androidx.compose.material3.MaterialTheme.typography.bodySmall,
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
            style = androidx.compose.material3.MaterialTheme.typography.titleMedium,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
            color = CqText,
        )
        Text(
            text = card.channel_title.orEmpty(),
            style = androidx.compose.material3.MaterialTheme.typography.bodySmall,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            color = CqMuted,
        )
    }
}

@Composable
fun VideoListRow(
    card: VideoCard,
    onOpen: (VideoCard) -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable { onOpen(card) }
            .padding(vertical = 10.dp),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            modifier = Modifier
                .width(88.dp)
                .aspectRatio(16f / 10f)
                .clip(RoundedCornerShape(8.dp))
                .background(CqElev2),
        ) {
            if (!card.thumb_url.isNullOrBlank()) {
                AsyncImage(
                    model = card.thumb_url,
                    contentDescription = null,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier.matchParentSize(),
                )
            }
        }
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = card.title.orEmpty(),
                style = androidx.compose.material3.MaterialTheme.typography.titleMedium,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                text = listOfNotNull(
                    card.channel_title?.takeIf { it.isNotBlank() },
                    formatDuration(card.duration_sec),
                ).joinToString(" В· "),
                style = androidx.compose.material3.MaterialTheme.typography.bodySmall,
            )
        }
    }
}

fun formatDuration(sec: Int?): String? {
    if (sec == null || sec <= 0) return null
    val h = sec / 3600
    val m = (sec % 3600) / 60
    val s = sec % 60
    return if (h > 0) "%d:%02d:%02d".format(h, m, s) else "%d:%02d".format(m, s)
}
