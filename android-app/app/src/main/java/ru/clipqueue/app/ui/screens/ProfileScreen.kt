package ru.clipqueue.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import ru.clipqueue.app.ApiClient
import ru.clipqueue.app.SessionStore
import ru.clipqueue.app.data.MeResponse
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
    onLoggedOut: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    var me by remember { mutableStateOf<MeResponse?>(null) }
    var syncMsg by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) {
        me = runCatching { api.me() }.getOrNull()
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(CqBg)
            .padding(horizontal = 20.dp),
    ) {
        Spacer(Modifier.height(18.dp))
        Text("Профиль", style = MaterialTheme.typography.titleLarge)
        Text(
            me?.user?.email ?: session.email ?: "—",
            style = MaterialTheme.typography.bodySmall,
            color = CqMuted,
        )
        Spacer(Modifier.height(16.dp))

        ProfileBlock(
            title = "YouTube",
            body = "Лайки и плейлисты синхронизируются при открытии приложения.",
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
        ) {
            Text(syncMsg ?: "Синхронизировать сейчас")
        }

        Spacer(Modifier.height(10.dp))
        Button(
            onClick = {
                session.clear()
                onLoggedOut()
            },
            modifier = Modifier.fillMaxWidth().height(48.dp),
            shape = RoundedCornerShape(12.dp),
            colors = ButtonDefaults.buttonColors(containerColor = CqElev, contentColor = CqText),
        ) {
            Text("Выйти")
        }

        Spacer(Modifier.weight(1f))
        BottomBar(selected = 2, onHome = onHome, onFolders = onFolders, onProfile = {})
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
