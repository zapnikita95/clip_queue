package ru.clipqueue.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
import kotlinx.coroutines.launch
import ru.clipqueue.app.ApiClient
import ru.clipqueue.app.data.TasteQuestionDto
import ru.clipqueue.app.data.TasteResponse
import ru.clipqueue.app.data.VideoCard
import ru.clipqueue.app.ui.theme.CqAccent
import ru.clipqueue.app.ui.theme.CqBorder
import ru.clipqueue.app.ui.theme.CqElev
import ru.clipqueue.app.ui.theme.CqMuted
import ru.clipqueue.app.ui.theme.CqText
import android.widget.Toast

@Composable
fun PendingRatingsDialog(
    api: ApiClient,
    items: List<VideoCard>,
    onDismiss: () -> Unit,
    onRated: () -> Unit = {},
) {
    if (items.isEmpty()) return
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    var index by remember { mutableIntStateOf(0) }
    var busy by remember { mutableStateOf(false) }
    val card = items.getOrNull(index) ?: return
    val remaining = items.size - index

    fun advanceOrClose() {
        if (index + 1 < items.size) {
            index += 1
        } else {
            onRated()
            onDismiss()
        }
    }

    fun rate(interest: Int?, skip: Boolean = false) {
        if (busy) return
        val id = card.video_id ?: return
        busy = true
        scope.launch {
            try {
                when {
                    skip -> runCatching {
                        api.patchLibrary(id, mapOf("rating_pending" to false))
                    }
                    interest != null -> runCatching { api.setInterest(id, interest) }
                }
                advanceOrClose()
            } finally {
                busy = false
            }
        }
    }

    AlertDialog(
        onDismissRequest = {
            // Soft dismiss: clear remaining so we don't spam every cold start
            scope.launch {
                items.drop(index).forEach { v ->
                    val id = v.video_id ?: return@forEach
                    runCatching { api.patchLibrary(id, mapOf("rating_pending" to false)) }
                }
                onDismiss()
            }
        },
        title = {
            Text(
                if (items.size == 1) "Как вам ролик?"
                else "Оценка просмотренных · $remaining",
            )
        },
        text = {
            Column {
                Text(
                    "После отметки «просмотрено» подскажем похожие в очереди.",
                    color = CqMuted,
                    style = MaterialTheme.typography.bodySmall,
                )
                Spacer(Modifier.height(12.dp))
                if (!card.thumb_url.isNullOrBlank()) {
                    AsyncImage(
                        model = card.thumb_url,
                        contentDescription = null,
                        contentScale = ContentScale.Crop,
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(140.dp)
                            .clip(RoundedCornerShape(12.dp))
                            .border(1.dp, CqBorder, RoundedCornerShape(12.dp)),
                    )
                    Spacer(Modifier.height(10.dp))
                }
                Text(
                    card.title.orEmpty().ifBlank { "Без названия" },
                    color = CqText,
                    style = MaterialTheme.typography.titleMedium,
                    maxLines = 3,
                )
                Text(
                    listOfNotNull(card.channel_title, card.duration_label).joinToString(" · "),
                    color = CqMuted,
                    style = MaterialTheme.typography.bodySmall,
                )
                Spacer(Modifier.height(14.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    RateChip("Зашло", enabled = !busy) { rate(2) }
                    RateChip("Норм", enabled = !busy) { rate(1) }
                    RateChip("Не то", enabled = !busy) { rate(-1) }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = { rate(null, skip = true) }, enabled = !busy) {
                Text("Пропустить")
            }
        },
        dismissButton = {
            TextButton(
                onClick = {
                    Toast.makeText(context, "Ок, без оценок", Toast.LENGTH_SHORT).show()
                    onDismiss()
                },
            ) { Text("Закрыть") }
        },
    )
}

@Composable
private fun RateChip(label: String, enabled: Boolean, onClick: () -> Unit) {
    Text(
        label,
        color = CqText,
        style = MaterialTheme.typography.labelLarge.copy(fontWeight = FontWeight.SemiBold),
        modifier = Modifier
            .clip(RoundedCornerShape(10.dp))
            .background(CqElev)
            .border(1.dp, CqBorder, RoundedCornerShape(10.dp))
            .clickable(enabled = enabled, onClick = onClick)
            .padding(horizontal = 14.dp, vertical = 10.dp),
    )
}

@Composable
fun TasteConfirmDialog(
    api: ApiClient,
    taste: TasteResponse,
    onDismiss: () -> Unit,
    onDone: () -> Unit = {},
) {
    val questions = taste.questions.orEmpty()
    if (questions.isEmpty()) return
    val scope = rememberCoroutineScope()
    var qIndex by remember { mutableIntStateOf(0) }
    var answers by remember { mutableStateOf(mapOf<String, String>()) }
    var busy by remember { mutableStateOf(false) }
    val q: TasteQuestionDto = questions.getOrNull(qIndex) ?: return
    val selected = answers[q.id.orEmpty()] ?: q.inferred.orEmpty()

    fun finish(skip: Boolean) {
        if (busy) return
        busy = true
        scope.launch {
            try {
                if (skip) {
                    api.confirmTaste(mapOf("skip" to true))
                } else {
                    api.confirmTaste(mapOf("answers" to answers))
                }
                onDone()
                onDismiss()
            } finally {
                busy = false
            }
        }
    }

    AlertDialog(
        onDismissRequest = { finish(skip = true) },
        title = { Text(taste.copy?.title ?: "Уточним вкус") },
        text = {
            Column {
                Text(
                    taste.copy?.subtitle
                        ?: "Подтвердите — или пропустите, будем опираться на историю.",
                    color = CqMuted,
                    style = MaterialTheme.typography.bodySmall,
                )
                Spacer(Modifier.height(12.dp))
                Text(
                    q.prompt.orEmpty(),
                    color = CqText,
                    style = MaterialTheme.typography.titleSmall,
                )
                Spacer(Modifier.height(8.dp))
                q.options.orEmpty().forEach { opt ->
                    val id = opt.id.orEmpty()
                    val on = selected == id
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 4.dp)
                            .clip(RoundedCornerShape(12.dp))
                            .background(if (on) CqAccent.copy(alpha = 0.18f) else CqElev)
                            .border(
                                1.dp,
                                if (on) CqAccent else CqBorder,
                                RoundedCornerShape(12.dp),
                            )
                            .clickable {
                                val key = q.id.orEmpty()
                                if (key.isNotBlank()) {
                                    answers = answers + (key to id)
                                }
                            }
                            .padding(12.dp),
                    ) {
                        Text(opt.label.orEmpty(), color = CqText)
                        if (!opt.hint.isNullOrBlank()) {
                            Text(opt.hint, color = CqMuted, style = MaterialTheme.typography.bodySmall)
                        }
                    }
                }
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    if (selected.isNotBlank() && !q.id.isNullOrBlank()) {
                        answers = answers + (q.id!! to selected)
                    }
                    if (qIndex + 1 < questions.size) {
                        qIndex += 1
                    } else {
                        finish(skip = false)
                    }
                },
                enabled = !busy,
            ) {
                Text(if (qIndex + 1 < questions.size) "Дальше" else "Готово")
            }
        },
        dismissButton = {
            TextButton(onClick = { finish(skip = true) }, enabled = !busy) {
                Text("Пропустить")
            }
        },
    )
}
