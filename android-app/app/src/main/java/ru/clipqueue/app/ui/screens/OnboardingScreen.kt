package ru.clipqueue.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
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
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import ru.clipqueue.app.ApiClient
import ru.clipqueue.app.SessionStore
import ru.clipqueue.app.ui.theme.CqAccent
import ru.clipqueue.app.ui.theme.CqBg
import ru.clipqueue.app.ui.theme.CqMuted
import ru.clipqueue.app.ui.theme.CqOnAccent
import ru.clipqueue.app.ui.theme.CqText

@Composable
fun OnboardingScreen(
    api: ApiClient,
    session: SessionStore,
    onDone: () -> Unit,
) {
    var step by remember { mutableIntStateOf(0) }
    val scope = rememberCoroutineScope()
    val pages = listOf(
        Triple(
            "Kyro",
            "Спокойное место для вашей очереди YouTube. Сохраняйте ролики и возвращайтесь к ним в нужный момент.",
            "Продолжить",
        ),
        Triple(
            "Синхронизация",
            "Мы бережно подтянем ваши лайки и плейлисты в одну библиотеку.",
            "Синхронизировать",
        ),
        Triple(
            "Папки и теги",
            "Разложите поток по темам — так случайные сохранения становятся осмысленной коллекцией.",
            "Продолжить",
        ),
        Triple(
            "Сохранение",
            "В YouTube нажмите «Поделиться» → Kyro. Видео появится в вашей библиотеке.",
            "Начать",
        ),
    )
    val (title, body, cta) = pages[step]

    Column(
        modifier = Modifier.fillMaxSize().background(CqBg).padding(24.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        Text("${step + 1} / ${pages.size}", color = CqMuted, style = MaterialTheme.typography.bodySmall)
        Spacer(Modifier.height(12.dp))
        Text(title, style = MaterialTheme.typography.titleLarge, color = CqText)
        Spacer(Modifier.height(12.dp))
        Text(body, style = MaterialTheme.typography.bodyLarge, color = CqMuted)
        Spacer(Modifier.height(28.dp))
        Button(
            onClick = {
                when (step) {
                    1 -> scope.launch {
                        runCatching { api.startYoutubeSync(full = false) }
                        step++
                    }
                    pages.lastIndex -> {
                        session.onboardingDone = true
                        onDone()
                    }
                    else -> step++
                }
            },
            modifier = Modifier.fillMaxWidth().height(52.dp),
            shape = RoundedCornerShape(14.dp),
            colors = ButtonDefaults.buttonColors(containerColor = CqAccent, contentColor = CqOnAccent),
        ) { Text(cta) }
        if (step < pages.lastIndex) {
            Spacer(Modifier.height(10.dp))
            OutlinedButton(
                onClick = {
                    session.onboardingDone = true
                    onDone()
                },
                modifier = Modifier.fillMaxWidth().height(48.dp),
                shape = RoundedCornerShape(14.dp),
            ) { Text("Пропустить") }
        }
    }
}
