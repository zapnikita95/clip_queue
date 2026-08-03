package ru.clipqueue.app.ui.screens

import android.content.Intent
import android.net.Uri
import android.widget.Toast
import androidx.browser.customtabs.CustomTabsIntent
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import ru.clipqueue.app.ApiClient
import ru.clipqueue.app.SessionStore
import ru.clipqueue.app.data.MeResponse
import ru.clipqueue.app.data.TagDto
import ru.clipqueue.app.ui.components.BottomBar
import ru.clipqueue.app.ui.theme.CqAccent
import ru.clipqueue.app.ui.theme.CqBg
import ru.clipqueue.app.ui.theme.CqBorder
import ru.clipqueue.app.ui.theme.CqElev
import ru.clipqueue.app.ui.theme.CqMuted
import ru.clipqueue.app.ui.theme.CqOk
import ru.clipqueue.app.ui.theme.CqText

@Composable
fun ProfileScreen(
    api: ApiClient,
    session: SessionStore,
    onHome: () -> Unit,
    onFolders: () -> Unit,
    onOpenHistory: () -> Unit,
    onLoggedOut: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    var me by remember { mutableStateOf<MeResponse?>(null) }
    var syncMsg by remember { mutableStateOf<String?>(null) }
    var tags by remember { mutableStateOf<List<TagDto>>(emptyList()) }
    var showNewFolder by remember { mutableStateOf(false) }
    var showNewTag by remember { mutableStateOf(false) }
    var draft by remember { mutableStateOf("") }

    fun reload() {
        scope.launch {
            me = runCatching { api.me() }.getOrNull()
            tags = runCatching { api.tags().tags.orEmpty() }.getOrDefault(emptyList())
        }
    }

    LaunchedEffect(Unit) { reload() }

    fun openWeb(path: String) {
        val url = api.baseUrl.trimEnd('/') + path
        CustomTabsIntent.Builder().build().launchUrl(context, Uri.parse(url))
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(CqBg)
            .padding(horizontal = 20.dp),
    ) {
        Spacer(Modifier.height(18.dp))
        Text("Ещё", style = MaterialTheme.typography.titleLarge)
        Text(
            me?.user?.email ?: session.email ?: "—",
            style = MaterialTheme.typography.bodySmall,
            color = CqMuted,
        )

        Column(
            modifier = Modifier
                .weight(1f)
                .verticalScroll(rememberScrollState()),
        ) {
            Spacer(Modifier.height(16.dp))
            ProfileBlock(
                title = "YouTube",
                body = "Лайки и плейлисты подтягиваются при открытии приложения.",
                chip = if (me?.youtube_connected == true) "подключено" else "не подключено",
                chipOk = me?.youtube_connected == true,
            )
            ProfileBlock(
                title = "Последний синк",
                body = me?.last_youtube_sync?.at?.ifBlank { null } ?: "ещё не было",
            )
            ProfileBlock(
                title = "Библиотека",
                body = "${me?.library_count ?: 0} сохранённых",
            )

            Spacer(Modifier.height(6.dp))
            Text("Папки и теги", style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(8.dp))
            OutlinedButton(
                onClick = { draft = ""; showNewFolder = true },
                modifier = Modifier.fillMaxWidth().height(48.dp),
                shape = RoundedCornerShape(12.dp),
            ) { Text("Создать папку") }
            Spacer(Modifier.height(8.dp))
            OutlinedButton(
                onClick = { draft = ""; showNewTag = true },
                modifier = Modifier.fillMaxWidth().height(48.dp),
                shape = RoundedCornerShape(12.dp),
            ) { Text("Создать тег") }
            Spacer(Modifier.height(8.dp))
            OutlinedButton(
                onClick = {
                    scope.launch {
                        val r = runCatching { api.seedTags() }.getOrNull()
                        tags = r?.tags.orEmpty().ifEmpty { tags }
                        Toast.makeText(context, "Базовые теги добавлены", Toast.LENGTH_SHORT).show()
                    }
                },
                modifier = Modifier.fillMaxWidth().height(48.dp),
                shape = RoundedCornerShape(12.dp),
            ) { Text("Добавить базовые теги") }
            if (tags.isNotEmpty()) {
                Spacer(Modifier.height(8.dp))
                Text(
                    tags.take(12).joinToString(" · ") { ((it.emoji ?: "") + " " + (it.name ?: "")).trim() },
                    color = CqMuted,
                    style = MaterialTheme.typography.bodySmall,
                )
            }

            OutlinedButton(
                onClick = onOpenHistory,
                modifier = Modifier.fillMaxWidth().height(48.dp),
                shape = RoundedCornerShape(12.dp),
            ) { Text("История сохранений (debug)") }
            Spacer(Modifier.height(14.dp))
            Text("Настройки с веба", style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(8.dp))
            OutlinedButton(
                onClick = { openWeb("/organize") },
                modifier = Modifier.fillMaxWidth().height(48.dp),
                shape = RoundedCornerShape(12.dp),
            ) { Text("Разложить по темам") }
            Spacer(Modifier.height(8.dp))
            OutlinedButton(
                onClick = { openWeb("/settings") },
                modifier = Modifier.fillMaxWidth().height(48.dp),
                shape = RoundedCornerShape(12.dp),
            ) { Text("Полные настройки (веб)") }
            Spacer(Modifier.height(8.dp))
            OutlinedButton(
                onClick = { openWeb("/search") },
                modifier = Modifier.fillMaxWidth().height(48.dp),
                shape = RoundedCornerShape(12.dp),
            ) { Text("Умный поиск (веб)") }

            Spacer(Modifier.height(8.dp))
            OutlinedButton(
                onClick = {
                    scope.launch {
                        syncMsg = "синк…"
                        val r = runCatching { api.startYoutubeSync(full = false) }.getOrNull()
                        syncMsg = if (r?.ok == true) "синк запущен" else (r?.error ?: "ошибка синка")
                        me = runCatching { api.me() }.getOrNull()
                    }
                },
                modifier = Modifier.fillMaxWidth().height(48.dp),
                shape = RoundedCornerShape(12.dp),
            ) { Text(syncMsg ?: "Синхронизировать сейчас") }

            Spacer(Modifier.height(10.dp))
            Button(
                onClick = {
                    session.clear()
                    onLoggedOut()
                },
                modifier = Modifier.fillMaxWidth().height(48.dp),
                shape = RoundedCornerShape(12.dp),
                colors = ButtonDefaults.buttonColors(containerColor = CqElev, contentColor = CqText),
            ) { Text("Выйти") }
            Spacer(Modifier.height(16.dp))
        }
        BottomBar(selected = 2, onHome = onHome, onFolders = onFolders, onProfile = {})
    }

    if (showNewFolder) {
        AlertDialog(
            onDismissRequest = { showNewFolder = false },
            title = { Text("Новая папка") },
            text = {
                OutlinedTextField(
                    value = draft,
                    onValueChange = { draft = it },
                    singleLine = true,
                    placeholder = { Text("Название") },
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = CqAccent,
                        unfocusedBorderColor = CqBorder,
                        focusedTextColor = CqText,
                        unfocusedTextColor = CqText,
                        cursorColor = CqAccent,
                    ),
                )
            },
            confirmButton = {
                TextButton(onClick = {
                    val name = draft.trim()
                    if (name.isEmpty()) return@TextButton
                    scope.launch {
                        val r = runCatching { api.createList(name) }.getOrNull()
                        showNewFolder = false
                        Toast.makeText(
                            context,
                            if (r?.ok == true) "Папка создана" else (r?.error ?: "Ошибка"),
                            Toast.LENGTH_SHORT,
                        ).show()
                    }
                }) { Text("Создать") }
            },
            dismissButton = {
                TextButton(onClick = { showNewFolder = false }) { Text("Отмена") }
            },
        )
    }
    if (showNewTag) {
        AlertDialog(
            onDismissRequest = { showNewTag = false },
            title = { Text("Новый тег") },
            text = {
                OutlinedTextField(
                    value = draft,
                    onValueChange = { draft = it },
                    singleLine = true,
                    placeholder = { Text("Название тега") },
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = CqAccent,
                        unfocusedBorderColor = CqBorder,
                        focusedTextColor = CqText,
                        unfocusedTextColor = CqText,
                        cursorColor = CqAccent,
                    ),
                )
            },
            confirmButton = {
                TextButton(onClick = {
                    val name = draft.trim()
                    if (name.isEmpty()) return@TextButton
                    scope.launch {
                        val r = runCatching { api.createTag(name) }.getOrNull()
                        showNewTag = false
                        if (r?.ok == true) reload()
                        Toast.makeText(
                            context,
                            if (r?.ok == true) "Тег создан" else (r?.error ?: "Ошибка"),
                            Toast.LENGTH_SHORT,
                        ).show()
                    }
                }) { Text("Создать") }
            },
            dismissButton = {
                TextButton(onClick = { showNewTag = false }) { Text("Отмена") }
            },
        )
    }
}

@Composable
private fun ProfileBlock(
    title: String,
    body: String,
    chip: String? = null,
    chipOk: Boolean = true,
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(bottom = 10.dp)
            .background(CqElev, RoundedCornerShape(14.dp))
            .border(1.dp, CqBorder, RoundedCornerShape(14.dp))
            .padding(14.dp),
    ) {
        Text(title, style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(4.dp))
        Text(body, style = MaterialTheme.typography.bodySmall, color = CqMuted)
        if (chip != null) {
            Spacer(Modifier.height(8.dp))
            Text(
                chip,
                color = if (chipOk) CqOk else CqAccent,
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}
