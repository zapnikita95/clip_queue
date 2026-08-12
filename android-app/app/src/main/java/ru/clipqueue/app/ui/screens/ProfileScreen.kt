package ru.clipqueue.app.ui.screens

import android.content.Intent
import android.net.Uri
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.browser.customtabs.CustomTabsIntent
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.HelpOutline
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
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
import androidx.compose.ui.Alignment
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import ru.clipqueue.app.ApiClient
import ru.clipqueue.app.SessionStore
import ru.clipqueue.app.data.MeResponse
import ru.clipqueue.app.data.TagDto
import ru.clipqueue.app.ui.TimeFormat
import ru.clipqueue.app.ui.components.BottomBar
import ru.clipqueue.app.ui.components.TagChip
import ru.clipqueue.app.ui.screens.FaqSparkleButton
import ru.clipqueue.app.ui.theme.CqAccent
import ru.clipqueue.app.ui.theme.CqBg
import ru.clipqueue.app.ui.theme.CqBorder
import ru.clipqueue.app.ui.theme.CqElev
import ru.clipqueue.app.ui.theme.CqMuted
import ru.clipqueue.app.ui.theme.CqOk
import ru.clipqueue.app.ui.theme.CqText

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun ProfileScreen(
    api: ApiClient,
    session: SessionStore,
    onHome: () -> Unit,
    onFolders: () -> Unit,
    onOpenHistory: () -> Unit,
    onOpenFaq: () -> Unit,
    onLoggedOut: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    var me by remember { mutableStateOf<MeResponse?>(null) }
    var syncMsg by remember { mutableStateOf<String?>(null) }
    var tags by remember { mutableStateOf<List<TagDto>>(emptyList()) }
    var showNewFolder by remember { mutableStateOf(false) }
    var showNewTag by remember { mutableStateOf(false) }
    var showTakeoutHelp by remember { mutableStateOf(false) }
    var takeoutMsg by remember { mutableStateOf<String?>(null) }
    var draft by remember { mutableStateOf("") }

    fun reload() {
        scope.launch {
            me = runCatching { api.me() }.getOrNull()
            tags = runCatching { api.tags().tags.orEmpty() }.getOrDefault(emptyList())
        }
    }
    LaunchedEffect(Unit) { reload() }

    fun openWeb(path: String) {
        CustomTabsIntent.Builder().build().launchUrl(context, Uri.parse(api.baseUrl.trimEnd('/') + path))
    }

    val takeoutPicker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            takeoutMsg = "читаю…"
            val text = withContext(Dispatchers.IO) {
                context.contentResolver.openInputStream(uri)?.bufferedReader()?.readText()
            }
            if (text.isNullOrBlank()) {
                takeoutMsg = "пустой файл"
                return@launch
            }
            val r = runCatching { api.uploadTakeout(text) }.getOrNull()
            takeoutMsg = if (r?.ok == true) "Takeout загружен" else (r?.error ?: "ошибка Takeout")
            me = runCatching { api.me() }.getOrNull()
            Toast.makeText(context, takeoutMsg, Toast.LENGTH_LONG).show()
        }
    }

    Column(modifier = Modifier.fillMaxSize().background(CqBg).padding(horizontal = 12.dp)) {
        Spacer(Modifier.height(14.dp))
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text("Настройки", style = MaterialTheme.typography.titleLarge)
                Text(
                    me?.user?.email ?: session.email ?: "—",
                    style = MaterialTheme.typography.bodySmall,
                    color = CqMuted,
                )
            }
            FaqSparkleButton(onClick = onOpenFaq)
        }

        Column(
            modifier = Modifier
                .weight(1f)
                .verticalScroll(rememberScrollState())
                .padding(bottom = 96.dp),
        ) {
            Spacer(Modifier.height(14.dp))
            ProfileBlock(
                "YouTube",
                "Мы бережно подтягиваем лайки и плейлисты, когда вы открываете приложение.",
                if (me?.youtube_connected == true) "подключено" else "нужно подключить",
                me?.youtube_connected == true,
            )
            ProfileBlock("Последнее обновление", TimeFormat.syncLocal(me?.last_youtube_sync?.at))
            ProfileBlock("Библиотека", "${me?.library_count ?: 0} сохранённых")

            Spacer(Modifier.height(8.dp))
            Text("Управление", style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(8.dp))
            OutlinedButton(onClick = { draft = ""; showNewFolder = true }, modifier = Modifier.fillMaxWidth().height(48.dp), shape = RoundedCornerShape(12.dp)) { Text("Создать папку") }
            Spacer(Modifier.height(8.dp))
            OutlinedButton(onClick = { draft = ""; showNewTag = true }, modifier = Modifier.fillMaxWidth().height(48.dp), shape = RoundedCornerShape(12.dp)) { Text("Создать тег") }
            Spacer(Modifier.height(8.dp))
            OutlinedButton(
                onClick = {
                    scope.launch {
                        tags = runCatching { api.seedTags().tags.orEmpty() }.getOrDefault(tags)
                        Toast.makeText(context, "Базовые теги добавлены", Toast.LENGTH_SHORT).show()
                    }
                },
                modifier = Modifier.fillMaxWidth().height(48.dp),
                shape = RoundedCornerShape(12.dp),
            ) { Text("Добавить базовые теги") }
            if (tags.isNotEmpty()) {
                Spacer(Modifier.height(10.dp))
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    tags.forEach { t ->
                        TagChip(listOfNotNull(t.emoji?.takeIf { it.isNotBlank() }, t.name).joinToString(" "))
                    }
                }
            }

            Spacer(Modifier.height(14.dp))
            Text("Синхронизация", style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(8.dp))
            OutlinedButton(
                onClick = {
                    scope.launch {
                        syncMsg = "Обновляем…"
                        val r = runCatching { api.startYoutubeSync(full = false) }.getOrNull()
                        syncMsg = if (r?.ok == true) "Обновление запущено" else (r?.error ?: "Не удалось обновить")
                        me = runCatching { api.me() }.getOrNull()
                    }
                },
                modifier = Modifier.fillMaxWidth().height(48.dp),
                shape = RoundedCornerShape(12.dp),
            ) { Text(syncMsg ?: "Обновить библиотеку") }
            Spacer(Modifier.height(8.dp))
            OutlinedButton(
                onClick = {
                    scope.launch {
                        syncMsg = "Полное обновление…"
                        val r = runCatching { api.startYoutubeSync(full = true) }.getOrNull()
                        syncMsg = if (r?.ok == true) "Полное обновление запущено" else (r?.error ?: "Не удалось обновить")
                        me = runCatching { api.me() }.getOrNull()
                    }
                },
                modifier = Modifier.fillMaxWidth().height(48.dp),
                shape = RoundedCornerShape(12.dp),
            ) { Text("Полное обновление") }
            Spacer(Modifier.height(8.dp))
            OutlinedButton(
                onClick = {
                    scope.launch {
                        val r = runCatching { api.startClassifyPending() }.getOrNull()
                        Toast.makeText(
                            context,
                            if (r?.ok == true) "Раскладываем необработанные видео по папкам" else (r?.error ?: "Не удалось запустить"),
                            Toast.LENGTH_SHORT,
                        ).show()
                    }
                },
                modifier = Modifier.fillMaxWidth().height(48.dp),
                shape = RoundedCornerShape(12.dp),
            ) { Text("Разложить необработанные") }

            Spacer(Modifier.height(14.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Takeout", style = MaterialTheme.typography.titleMedium)
                Spacer(Modifier.size(8.dp))
                Icon(
                    Icons.Outlined.HelpOutline,
                    contentDescription = "Что такое Takeout",
                    tint = CqMuted,
                    modifier = Modifier.size(22.dp).clickable { showTakeoutHelp = true },
                )
            }
            Spacer(Modifier.height(8.dp))
            OutlinedButton(
                onClick = { takeoutPicker.launch("application/json") },
                modifier = Modifier.fillMaxWidth().height(48.dp),
                shape = RoundedCornerShape(12.dp),
            ) { Text(takeoutMsg ?: "Загрузить watch-history.json") }

            Spacer(Modifier.height(14.dp))
            Text("Ещё", style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(8.dp))
            OutlinedButton(onClick = onOpenHistory, modifier = Modifier.fillMaxWidth().height(48.dp), shape = RoundedCornerShape(12.dp)) { Text("История сохранений") }
            Spacer(Modifier.height(8.dp))
            OutlinedButton(onClick = { openWeb("/organize") }, modifier = Modifier.fillMaxWidth().height(48.dp), shape = RoundedCornerShape(12.dp)) { Text("Редактор раскладки (веб)") }
            Spacer(Modifier.height(8.dp))
            OutlinedButton(onClick = { openWeb("/search") }, modifier = Modifier.fillMaxWidth().height(48.dp), shape = RoundedCornerShape(12.dp)) { Text("Умный поиск") }
            Spacer(Modifier.height(8.dp))
            OutlinedButton(
                onClick = {
                    context.startActivity(
                        Intent(Intent.ACTION_VIEW, Uri.parse("https://movie-planner.ru/?open_login=1")),
                    )
                },
                modifier = Modifier.fillMaxWidth().height(48.dp),
                shape = RoundedCornerShape(12.dp),
            ) { Text("Кино — Movie Planner") }

            Spacer(Modifier.height(10.dp))
            Button(
                onClick = { session.clear(); onLoggedOut() },
                modifier = Modifier.fillMaxWidth().height(48.dp),
                shape = RoundedCornerShape(12.dp),
                colors = ButtonDefaults.buttonColors(containerColor = CqElev, contentColor = CqText),
            ) { Text("Выйти") }
            Spacer(Modifier.height(16.dp))
        }
        BottomBar(selected = 2, onHome = onHome, onFolders = onFolders, onProfile = {})
    }

    if (showTakeoutHelp) {
        AlertDialog(
            onDismissRequest = { showTakeoutHelp = false },
            title = { Text("Что такое Takeout?") },
            text = {
                Text(
                    "Google Takeout — выгрузка ваших данных YouTube. Скачайте watch-history.json " +
                        "(история просмотров) на takeout.google.com, затем загрузите сюда. " +
                        "Мы отметим уже просмотренные ролики в вашей библиотеке.",
                )
            },
            confirmButton = { TextButton(onClick = { showTakeoutHelp = false }) { Text("Понятно") } },
        )
    }
    if (showNewFolder) {
        NameDialog("Новая папка", draft, { draft = it }, { showNewFolder = false }) {
            val name = draft.trim(); if (name.isEmpty()) return@NameDialog
            scope.launch {
                val r = runCatching { api.createList(name) }.getOrNull()
                showNewFolder = false
                Toast.makeText(context, if (r?.ok == true) "Папка создана" else (r?.error ?: "Ошибка"), Toast.LENGTH_SHORT).show()
            }
        }
    }
    if (showNewTag) {
        NameDialog("Новый тег", draft, { draft = it }, { showNewTag = false }) {
            val name = draft.trim(); if (name.isEmpty()) return@NameDialog
            scope.launch {
                val r = runCatching { api.createTag(name) }.getOrNull()
                showNewTag = false
                if (r?.ok == true) reload()
                Toast.makeText(context, if (r?.ok == true) "Тег создан" else (r?.error ?: "Ошибка"), Toast.LENGTH_SHORT).show()
            }
        }
    }
}

@Composable
private fun NameDialog(title: String, value: String, onChange: (String) -> Unit, onDismiss: () -> Unit, onConfirm: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = {
            OutlinedTextField(
                value = value, onValueChange = onChange, singleLine = true, placeholder = { Text("Название") },
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = CqAccent, unfocusedBorderColor = CqBorder,
                    focusedTextColor = CqText, unfocusedTextColor = CqText, cursorColor = CqAccent,
                ),
            )
        },
        confirmButton = { TextButton(onClick = onConfirm) { Text("Создать") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Отмена") } },
    )
}

@Composable
private fun ProfileBlock(title: String, body: String, chip: String? = null, chipOk: Boolean = true) {
    Column(
        modifier = Modifier.fillMaxWidth().padding(bottom = 10.dp)
            .background(CqElev, RoundedCornerShape(14.dp))
            .border(1.dp, CqBorder, RoundedCornerShape(14.dp))
            .padding(14.dp),
    ) {
        Text(title, style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(4.dp))
        Text(body, style = MaterialTheme.typography.bodySmall, color = CqMuted)
        if (chip != null) {
            Spacer(Modifier.height(8.dp))
            Text(chip, color = if (chipOk) CqOk else CqAccent, style = MaterialTheme.typography.bodySmall)
        }
    }
}
