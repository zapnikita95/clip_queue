package ru.clipqueue.app.ui

import android.widget.Toast
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Checkbox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
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
import ru.clipqueue.app.data.ListCard
import ru.clipqueue.app.data.TagDto
import ru.clipqueue.app.data.VideoCard
import ru.clipqueue.app.ui.theme.CqAccent
import ru.clipqueue.app.ui.theme.CqMuted

@Composable
fun TagPickerDialog(
    api: ApiClient,
    card: VideoCard,
    cache: AppCache? = null,
    onDismiss: () -> Unit,
    onChanged: () -> Unit = {},
) {
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    var loading by remember { mutableStateOf(true) }
    var allTags by remember { mutableStateOf<List<TagDto>>(emptyList()) }
    var selected by remember { mutableStateOf(setOf<Int>()) }
    var newName by remember { mutableStateOf("") }
    val videoId = card.video_id.orEmpty()

    LaunchedEffect(videoId) {
        loading = true
        val detail = runCatching { api.video(videoId) }.getOrNull()?.item
        allTags = runCatching { api.tags(onlyUsed = false) }.getOrNull()?.tags.orEmpty()
        selected = (detail?.user_tags ?: card.user_tags).orEmpty().mapNotNull { it.id }.toSet()
        loading = false
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Теги") },
        text = {
            Column(modifier = Modifier.heightIn(max = 420.dp)) {
                Text(
                    card.title.orEmpty(),
                    style = MaterialTheme.typography.bodySmall,
                    color = CqMuted,
                    maxLines = 2,
                )
                Spacer(Modifier.height(8.dp))
                when {
                    loading -> Text("Загрузка…", color = CqMuted)
                    allTags.isEmpty() -> Text("Тегов пока нет — создайте ниже", color = CqMuted)
                    else -> {
                        Column(
                            modifier = Modifier
                                .heightIn(max = 260.dp)
                                .verticalScroll(rememberScrollState()),
                            verticalArrangement = Arrangement.spacedBy(2.dp),
                        ) {
                            allTags.forEach { t ->
                                val id = t.id ?: return@forEach
                                val on = id in selected
                                val label = listOfNotNull(
                                    t.emoji?.takeIf { it.isNotBlank() },
                                    t.name,
                                ).joinToString(" ")
                                Row(
                                    modifier = Modifier
                                        .fillMaxWidth()
                                        .clickable {
                                            scope.launch {
                                                val r = if (on) {
                                                    runCatching { api.untagVideo(videoId, id) }.getOrNull()
                                                } else {
                                                    runCatching { api.tagVideo(videoId, id) }.getOrNull()
                                                }
                                                if (r?.ok == true) {
                                                    selected = if (on) selected - id else selected + id
                                                    cache?.invalidateAll()
                                                    onChanged()
                                                } else {
                                                    Toast.makeText(
                                                        context,
                                                        r?.error ?: "Ошибка",
                                                        Toast.LENGTH_SHORT,
                                                    ).show()
                                                }
                                            }
                                        }
                                        .padding(vertical = 4.dp),
                                    verticalAlignment = Alignment.CenterVertically,
                                ) {
                                    Checkbox(checked = on, onCheckedChange = null)
                                    Text(label, modifier = Modifier.padding(start = 4.dp))
                                }
                            }
                        }
                    }
                }
                Spacer(Modifier.height(10.dp))
                OutlinedTextField(
                    value = newName,
                    onValueChange = { newName = it },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                    placeholder = { Text("Новый тег") },
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    val name = newName.trim()
                    if (name.isBlank()) {
                        onDismiss()
                        return@TextButton
                    }
                    scope.launch {
                        val created = runCatching { api.createTag(name) }.getOrNull()
                        val tid = created?.tag?.id
                        if (created?.ok == true && tid != null) {
                            runCatching { api.tagVideo(videoId, tid) }
                            cache?.invalidateAll()
                            onChanged()
                            Toast.makeText(context, "Тег добавлен", Toast.LENGTH_SHORT).show()
                            onDismiss()
                        } else {
                            Toast.makeText(
                                context,
                                created?.error ?: "Не создалось",
                                Toast.LENGTH_SHORT,
                            ).show()
                        }
                    }
                },
            ) {
                Text(if (newName.isBlank()) "Готово" else "Создать", color = CqAccent)
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Закрыть") }
        },
    )
}

@Composable
fun MovePickerDialog(
    api: ApiClient,
    card: VideoCard,
    cache: AppCache? = null,
    onDismiss: () -> Unit,
    onChanged: () -> Unit = {},
) {
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    var loading by remember { mutableStateOf(true) }
    var folders by remember { mutableStateOf<List<ListCard>>(emptyList()) }
    var inLists by remember { mutableStateOf(setOf<Int>()) }
    var newTitle by remember { mutableStateOf("") }
    val videoId = card.video_id.orEmpty()

    LaunchedEffect(videoId) {
        loading = true
        val detail = runCatching { api.video(videoId) }.getOrNull()?.item
        folders = runCatching { api.lists() }.getOrNull()?.lists.orEmpty()
            .sortedByDescending { it.count ?: 0 }
        inLists = (detail?.in_lists ?: card.in_lists).orEmpty().mapNotNull { it.id }.toSet()
        loading = false
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Перенести") },
        text = {
            Column(modifier = Modifier.heightIn(max = 420.dp)) {
                Text(
                    card.title.orEmpty(),
                    style = MaterialTheme.typography.bodySmall,
                    color = CqMuted,
                    maxLines = 2,
                )
                Spacer(Modifier.height(8.dp))
                if (loading) {
                    Text("Загрузка…", color = CqMuted)
                } else {
                    Column(
                        modifier = Modifier
                            .heightIn(max = 260.dp)
                            .verticalScroll(rememberScrollState()),
                        verticalArrangement = Arrangement.spacedBy(2.dp),
                    ) {
                        folders.forEach { folder ->
                            val id = folder.id ?: return@forEach
                            val on = id in inLists
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable {
                                        scope.launch {
                                            val r = if (on) {
                                                runCatching { api.removeFromList(id, videoId) }.getOrNull()
                                            } else {
                                                runCatching { api.addToList(id, videoId) }.getOrNull()
                                            }
                                            if (r?.ok == true) {
                                                inLists = if (on) inLists - id else inLists + id
                                                cache?.invalidateAll()
                                                onChanged()
                                            } else {
                                                Toast.makeText(
                                                    context,
                                                    r?.error ?: "Ошибка",
                                                    Toast.LENGTH_SHORT,
                                                ).show()
                                            }
                                        }
                                    }
                                    .padding(vertical = 6.dp),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Checkbox(checked = on, onCheckedChange = null)
                                Text(
                                    "${folder.title.orEmpty()} · ${folder.count ?: 0} видео",
                                    modifier = Modifier.padding(start = 4.dp),
                                )
                            }
                        }
                    }
                }
                Spacer(Modifier.height(10.dp))
                OutlinedTextField(
                    value = newTitle,
                    onValueChange = { newTitle = it },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                    placeholder = { Text("Новая папка") },
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    val title = newTitle.trim()
                    if (title.isBlank()) {
                        onDismiss()
                        return@TextButton
                    }
                    scope.launch {
                        val created = runCatching { api.createList(title) }.getOrNull()
                        val lid = created?.list?.id
                        if (created?.ok == true && lid != null) {
                            runCatching { api.addToList(lid, videoId) }
                            cache?.invalidateAll()
                            onChanged()
                            Toast.makeText(
                                context,
                                "Перенесено в «$title»",
                                Toast.LENGTH_SHORT,
                            ).show()
                            onDismiss()
                        } else {
                            Toast.makeText(
                                context,
                                created?.error ?: "Не создалось",
                                Toast.LENGTH_SHORT,
                            ).show()
                        }
                    }
                },
            ) {
                Text(
                    if (newTitle.isBlank()) "Готово" else "Создать папку",
                    color = CqAccent,
                )
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Закрыть") }
        },
    )
}
