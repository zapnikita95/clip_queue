package ru.clipqueue.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
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
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import ru.clipqueue.app.ApiClient
import ru.clipqueue.app.SessionStore
import ru.clipqueue.app.ui.theme.CqAccent
import ru.clipqueue.app.ui.theme.CqBg
import ru.clipqueue.app.ui.theme.CqBorder
import ru.clipqueue.app.ui.theme.CqElev
import ru.clipqueue.app.ui.theme.CqMuted
import ru.clipqueue.app.ui.theme.CqOnAccent
import ru.clipqueue.app.ui.theme.CqText

private data class PurposeChoice(val id: String, val label: String, val hint: String)

private val PurposeChoices = listOf(
    PurposeChoice("study", "Учёба", "Детальные направления: языки, лекции, экзамены…"),
    PurposeChoice("work", "Работа", "Карьера, продуктивность, инструменты"),
    PurposeChoice("entertainment", "Развлечение", "Кино, юмор, спорт и широкий досуг"),
)

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun OnboardingScreen(
    api: ApiClient,
    session: SessionStore,
    onDone: () -> Unit,
) {
    var step by remember { mutableIntStateOf(0) }
    var selected by remember { mutableStateOf(setOf("entertainment")) }
    var saving by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val pages = listOf(
        Triple(
            "Kyro",
            "Спокойное место для вашей библиотеки YouTube. Сохраняйте ролики и возвращайтесь к ним в нужный момент.",
            "Продолжить",
        ),
        // step 1 = purposes (handled separately)
        Triple(
            "Синхронизация",
            "Мы бережно подтянем ваши лайки и плейлисты в одну библиотеку.",
            "Синхронизировать",
        ),
        Triple(
            "Ваша спецпапка",
            "Плейлист «смотреть позже» или Listen later — inbox желаемого. Из него Kyro собирает блок «Сейчас».",
            "Продолжить",
        ),
        Triple(
            "Папки и теги",
            "Разложите поток по темам — так случайные сохранения становятся планом, а не складом ссылок.",
            "Продолжить",
        ),
        Triple(
            "Сохранение",
            "В YouTube нажмите «Поделиться» → Kyro. Видео появится в библиотеке; пуш подскажет папку.",
            "Начать",
        ),
    )
    // Visual steps: intro + purposes + rest
    val totalSteps = pages.size + 1
    val displayStep = if (step == 0) 1 else if (step == 1) 2 else step + 1

    Column(
        modifier = Modifier.fillMaxSize().background(CqBg).padding(24.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        Text("$displayStep / $totalSteps", color = CqMuted, style = MaterialTheme.typography.bodySmall)
        Spacer(Modifier.height(12.dp))

        if (step == 1) {
            Text("Зачем тебе Kyro?", style = MaterialTheme.typography.titleLarge, color = CqText)
            Spacer(Modifier.height(8.dp))
            Text(
                "Можно выбрать несколько. От этого зависят папки и как раскладываются сохранения — для учёбы направления подробнее.",
                style = MaterialTheme.typography.bodyLarge,
                color = CqMuted,
            )
            Spacer(Modifier.height(20.dp))
            FlowRow(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                PurposeChoices.forEach { choice ->
                    val on = choice.id in selected
                    Column(
                        modifier = Modifier
                            .clip(RoundedCornerShape(14.dp))
                            .background(if (on) CqAccent.copy(alpha = 0.14f) else CqElev)
                            .border(
                                width = 1.dp,
                                color = if (on) CqAccent else CqBorder,
                                shape = RoundedCornerShape(14.dp),
                            )
                            .clickable {
                                selected = if (on) {
                                    if (selected.size <= 1) selected else selected - choice.id
                                } else {
                                    selected + choice.id
                                }
                            }
                            .padding(horizontal = 14.dp, vertical = 12.dp),
                    ) {
                        Text(
                            choice.label,
                            color = CqText,
                            fontWeight = if (on) FontWeight.SemiBold else FontWeight.Normal,
                        )
                        Spacer(Modifier.height(4.dp))
                        Text(choice.hint, color = CqMuted, style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
            Spacer(Modifier.height(28.dp))
            Button(
                onClick = {
                    if (saving) return@Button
                    saving = true
                    scope.launch {
                        runCatching {
                            api.setPrefs(
                                mapOf(
                                    "use_purposes" to selected.toList(),
                                    "purposes_onboarding_done" to true,
                                ),
                            )
                        }
                        saving = false
                        step++
                    }
                },
                enabled = selected.isNotEmpty() && !saving,
                modifier = Modifier.fillMaxWidth().height(52.dp),
                shape = RoundedCornerShape(14.dp),
                colors = ButtonDefaults.buttonColors(containerColor = CqAccent, contentColor = CqOnAccent),
            ) { Text(if (saving) "Сохраняю…" else "Продолжить") }
            Spacer(Modifier.height(10.dp))
            OutlinedButton(
                onClick = {
                    scope.launch {
                        runCatching {
                            api.setPrefs(
                                mapOf(
                                    "use_purposes" to listOf("entertainment"),
                                    "purposes_onboarding_done" to true,
                                ),
                            )
                        }
                        step++
                    }
                },
                modifier = Modifier.fillMaxWidth().height(48.dp),
                shape = RoundedCornerShape(14.dp),
            ) { Text("Пропустить") }
        } else {
            val pageIndex = if (step == 0) 0 else step - 1
            val (title, body, cta) = pages[pageIndex]
            Text(title, style = MaterialTheme.typography.titleLarge, color = CqText)
            Spacer(Modifier.height(12.dp))
            Text(body, style = MaterialTheme.typography.bodyLarge, color = CqMuted)
            Spacer(Modifier.height(28.dp))
            Button(
                onClick = {
                    when (step) {
                        0 -> step = 1
                        2 -> scope.launch {
                            runCatching { api.startYoutubeSync(full = false) }
                            step++
                        }
                        totalSteps - 1 -> {
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
            if (step < totalSteps - 1) {
                Spacer(Modifier.height(10.dp))
                OutlinedButton(
                    onClick = {
                        if (step == 0) {
                            // skip intro → purposes still asked
                            step = 1
                        } else {
                            scope.launch {
                                if (step == 1 || !session.onboardingDone) {
                                    runCatching {
                                        api.setPrefs(
                                            mapOf(
                                                "use_purposes" to listOf("entertainment"),
                                                "purposes_onboarding_done" to true,
                                            ),
                                        )
                                    }
                                }
                                session.onboardingDone = true
                                onDone()
                            }
                        }
                    },
                    modifier = Modifier.fillMaxWidth().height(48.dp),
                    shape = RoundedCornerShape(14.dp),
                ) { Text("Пропустить") }
            }
        }
    }
}
