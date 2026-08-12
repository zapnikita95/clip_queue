package ru.clipqueue.app.ui.screens

import android.content.Intent
import android.net.Uri
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.browser.customtabs.CustomTabsIntent
import androidx.compose.foundation.background
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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.HelpOutline
import androidx.compose.material.icons.automirrored.outlined.KeyboardArrowRight
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
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
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
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
import ru.clipqueue.app.ui.theme.CqAccent
import ru.clipqueue.app.ui.theme.CqBg
import ru.clipqueue.app.ui.theme.CqBorder
import ru.clipqueue.app.ui.theme.CqElev
import ru.clipqueue.app.ui.theme.CqMuted
import ru.clipqueue.app.ui.theme.CqOk
import ru.clipqueue.app.ui.theme.CqText
import ru.clipqueue.app.ui.theme.CqWhisper
import ru.clipqueue.app.ui.theme.KyroFont

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
    var tagsExpanded by remember { mutableStateOf(false) }

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

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(CqBg)
            .padding(horizontal = 16.dp),
    ) {
        Spacer(Modifier.height(12.dp))
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    "Профиль",
                    style = MaterialTheme.typography.titleLarge,
                    fontFamily = KyroFont,
                )
                Text(
                    me?.user?.email ?: session.email ?: "—",
                    style = MaterialTheme.typography.bodySmall,
                    color = CqMuted,
                    maxLines = 1,
                )
            }
            Icon(
                Icons.AutoMirrored.Outlined.HelpOutline,
                contentDescription = "Справка",
                tint = CqMuted,
                modifier = Modifier
                    .size(40.dp)
                    .clickable(onClick = onOpenFaq)
                    .padding(8.dp),
            )
        }

        Column(
            modifier = Modifier
                .weight(1f)
                .verticalScroll(rememberScrollState())
                .padding(bottom = 72.dp),
        ) {
            Spacer(Modifier.height(18.dp))

            // Status — compact facts, no framed cards
            SettingsSectionLabel("Аккаунт")
            SettingsGroup {
                SettingsValueRow(
                    title = "YouTube",
                    value = if (me?.youtube_connected == true) "подключено" else "не подключено",
                    valueColor = if (me?.youtube_connected == true) CqOk else CqMuted,
                )
                SettingsDivider()
                SettingsValueRow(
                    title = "Обновление",
                    value = TimeFormat.syncLocal(me?.last_youtube_sync?.at).ifBlank { "—" },
                )
                SettingsDivider()
                SettingsValueRow(
                    title = "В библиотеке",
                    value = "${me?.library_count ?: 0}",
                )
            }

            Spacer(Modifier.height(20.dp))
            SettingsSectionLabel("Организация")
            SettingsGroup {
                SettingsNavRow("Новая папка") {
                    draft = ""
                    showNewFolder = true
                }
                SettingsDivider()
                SettingsNavRow("Новый тег") {
                    draft = ""
                    showNewTag = true
                }
                SettingsDivider()
                SettingsNavRow("Добавить базовые теги") {
                    scope.launch {
                        tags = runCatching { api.seedTags().tags.orEmpty() }.getOrDefault(tags)
                        Toast.makeText(context, "Базовые теги добавлены", Toast.LENGTH_SHORT).show()
                    }
                }
                if (tags.isNotEmpty()) {
                    SettingsDivider()
                    SettingsNavRow(
                        title = "Теги",
                        trailing = "${tags.size}",
                        showChevron = true,
                    ) { tagsExpanded = !tagsExpanded }
                }
            }
            if (tagsExpanded && tags.isNotEmpty()) {
                Spacer(Modifier.height(10.dp))
                FlowRow(
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                    modifier = Modifier.padding(horizontal = 2.dp),
                ) {
                    tags.forEach { t ->
                        TagChip(
                            listOfNotNull(t.emoji?.takeIf { it.isNotBlank() }, t.name).joinToString(" "),
                        )
                    }
                }
            }

            Spacer(Modifier.height(20.dp))
            SettingsSectionLabel("Синхронизация")
            SettingsGroup {
                SettingsNavRow(syncMsg ?: "Обновить библиотеку") {
                    scope.launch {
                        syncMsg = "Обновляем…"
                        val r = runCatching { api.startYoutubeSync(full = false) }.getOrNull()
                        syncMsg = if (r?.ok == true) "Обновление запущено" else (r?.error ?: "Не удалось обновить")
                        me = runCatching { api.me() }.getOrNull()
                    }
                }
                SettingsDivider()
                SettingsNavRow("Полное обновление") {
                    scope.launch {
                        syncMsg = "Полное обновление…"
                        val r = runCatching { api.startYoutubeSync(full = true) }.getOrNull()
                        syncMsg = if (r?.ok == true) "Полное обновление запущено" else (r?.error ?: "Не удалось обновить")
                        me = runCatching { api.me() }.getOrNull()
                    }
                }
                SettingsDivider()
                SettingsNavRow("Разложить необработанные") {
                    scope.launch {
                        val r = runCatching { api.startClassifyPending() }.getOrNull()
                        Toast.makeText(
                            context,
                            if (r?.ok == true) {
                                "Раскладываем необработанные видео по папкам"
                            } else {
                                (r?.error ?: "Не удалось запустить")
                            },
                            Toast.LENGTH_SHORT,
                        ).show()
                    }
                }
                SettingsDivider()
                SettingsNavRow(
                    title = takeoutMsg ?: "Загрузить Takeout",
                    trailing = null,
                    leadingHelp = { showTakeoutHelp = true },
                ) { takeoutPicker.launch("application/json") }
            }

            Spacer(Modifier.height(20.dp))
            SettingsSectionLabel("Ещё")
            SettingsGroup {
                SettingsNavRow("История сохранений", onClick = onOpenHistory)
                SettingsDivider()
                SettingsNavRow("Редактор раскладки") { openWeb("/organize") }
                SettingsDivider()
                SettingsNavRow("Умный поиск") { openWeb("/search") }
                SettingsDivider()
                SettingsNavRow("Movie Planner") {
                    context.startActivity(
                        Intent(Intent.ACTION_VIEW, Uri.parse("https://movie-planner.ru/?open_login=1")),
                    )
                }
            }

            Spacer(Modifier.height(22.dp))
            Text(
                "Выйти",
                color = CqWhisper,
                fontFamily = KyroFont,
                fontWeight = FontWeight.Medium,
                fontSize = 15.sp,
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(10.dp))
                    .clickable {
                        session.clear()
                        onLoggedOut()
                    }
                    .padding(vertical = 14.dp)
                    .padding(horizontal = 4.dp),
            )
            Spacer(Modifier.height(12.dp))
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
private fun SettingsSectionLabel(text: String) {
    Text(
        text.uppercase(),
        color = CqMuted,
        fontFamily = KyroFont,
        fontWeight = FontWeight.Medium,
        fontSize = 11.sp,
        letterSpacing = 0.6.sp,
        modifier = Modifier.padding(start = 4.dp, bottom = 8.dp),
    )
}

@Composable
private fun SettingsGroup(content: @Composable () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(CqElev),
    ) {
        content()
    }
}

@Composable
private fun SettingsDivider() {
    HorizontalDivider(
        modifier = Modifier.padding(start = 14.dp),
        thickness = 0.5.dp,
        color = CqBorder,
    )
}

@Composable
private fun SettingsValueRow(
    title: String,
    value: String,
    valueColor: androidx.compose.ui.graphics.Color = CqMuted,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 14.dp, vertical = 13.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(title, color = CqText, fontFamily = KyroFont, fontSize = 15.sp)
        Text(value, color = valueColor, fontFamily = KyroFont, fontSize = 13.sp)
    }
}

@Composable
private fun SettingsNavRow(
    title: String,
    trailing: String? = null,
    showChevron: Boolean = true,
    leadingHelp: (() -> Unit)? = null,
    onClick: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 14.dp, vertical = 13.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            title,
            color = CqText,
            fontFamily = KyroFont,
            fontSize = 15.sp,
            modifier = Modifier.weight(1f),
            maxLines = 1,
        )
        if (leadingHelp != null) {
            Icon(
                Icons.AutoMirrored.Outlined.HelpOutline,
                contentDescription = "Подсказка",
                tint = CqMuted,
                modifier = Modifier
                    .size(28.dp)
                    .clickable(onClick = leadingHelp)
                    .padding(4.dp),
            )
            Spacer(Modifier.width(4.dp))
        }
        if (!trailing.isNullOrBlank()) {
            Text(trailing, color = CqMuted, fontFamily = KyroFont, fontSize = 13.sp)
            Spacer(Modifier.width(4.dp))
        }
        if (showChevron) {
            Icon(
                Icons.AutoMirrored.Outlined.KeyboardArrowRight,
                contentDescription = null,
                tint = CqMuted.copy(alpha = 0.7f),
                modifier = Modifier.size(20.dp),
            )
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
