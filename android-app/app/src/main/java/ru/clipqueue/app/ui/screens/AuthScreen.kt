package ru.clipqueue.app.ui.screens

import android.net.Uri
import androidx.browser.customtabs.CustomTabsIntent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import ru.clipqueue.app.ApiClient
import ru.clipqueue.app.SessionStore
import ru.clipqueue.app.ui.theme.CqAccent
import ru.clipqueue.app.ui.theme.CqBg
import ru.clipqueue.app.ui.theme.CqElev
import ru.clipqueue.app.ui.theme.CqMuted
import ru.clipqueue.app.ui.theme.CqOnAccent
import ru.clipqueue.app.ui.theme.CqText
import ru.clipqueue.app.ui.theme.CqWhisper

@Composable
fun AuthScreen(
    api: ApiClient,
    session: SessionStore,
    onLoggedIn: () -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(
                Brush.radialGradient(
                    colors = listOf(CqText.copy(alpha = 0.08f), CqBg),
                    radius = 700f,
                ),
            )
            .padding(28.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Spacer(Modifier.height(72.dp))
        Box(
            modifier = Modifier
                .size(72.dp)
                .clip(RoundedCornerShape(18.dp))
                .background(CqElev),
            contentAlignment = Alignment.Center,
        ) {
            Text("Kyro", color = CqText, style = MaterialTheme.typography.labelSmall)
        }
        Spacer(Modifier.height(20.dp))
        Text("Kyro", style = MaterialTheme.typography.displayLarge)
        Spacer(Modifier.height(10.dp))
        Text(
            text = "YouTube → Поделиться → Kyro",
            style = MaterialTheme.typography.bodyMedium,
            color = CqMuted,
            textAlign = TextAlign.Center,
        )
        Spacer(Modifier.height(36.dp))
        Button(
            onClick = {
                val intent = CustomTabsIntent.Builder().build()
                intent.launchUrl(context, Uri.parse(api.googleStartUrl()))
            },
            enabled = !busy,
            modifier = Modifier.fillMaxWidth().height(48.dp),
            shape = RoundedCornerShape(12.dp),
            colors = ButtonDefaults.buttonColors(containerColor = CqAccent, contentColor = CqOnAccent),
        ) {
            Text("Войти через Google", fontWeight = FontWeight.Bold)
        }
        Spacer(Modifier.height(10.dp))
        OutlinedButton(
            onClick = {
                scope.launch {
                    busy = true
                    error = null
                    try {
                        val r = api.devLogin()
                        if (r.ok == true && !r.token.isNullOrBlank()) {
                            session.token = r.token
                            session.email = r.user?.email
                            onLoggedIn()
                        } else {
                            error = r.error ?: "DEV_LOGIN недоступен на проде"
                        }
                    } catch (e: Exception) {
                        error = e.message ?: "Ошибка входа"
                    } finally {
                        busy = false
                    }
                }
            },
            enabled = !busy,
            modifier = Modifier.fillMaxWidth().height(48.dp),
            shape = RoundedCornerShape(12.dp),
        ) {
            Text("Dev login")
        }
        error?.let {
            Spacer(Modifier.height(16.dp))
            Text(it, color = CqWhisper, style = MaterialTheme.typography.bodySmall)
        }
    }
}
