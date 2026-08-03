package ru.clipqueue.app.ui.screens

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.expandVertically
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.shrinkVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
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
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import ru.clipqueue.app.ui.KyroCopy
import ru.clipqueue.app.ui.theme.CqBg
import ru.clipqueue.app.ui.theme.CqBorder
import ru.clipqueue.app.ui.theme.CqElev
import ru.clipqueue.app.ui.theme.CqMuted
import ru.clipqueue.app.ui.theme.CqText

@Composable
fun FaqScreen(onBack: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(CqBg)
            .padding(horizontal = 20.dp),
    ) {
        Spacer(Modifier.height(14.dp))
        Text(
            "← Настройки",
            color = CqMuted,
            style = MaterialTheme.typography.bodySmall,
            modifier = Modifier.clickable(onClick = onBack),
        )
        Spacer(Modifier.height(12.dp))
        Text("Вопросы и ответы", style = MaterialTheme.typography.titleLarge)
        Text(
            "Спокойные ответы о Kyro и вашей библиотеке",
            color = CqMuted,
            style = MaterialTheme.typography.bodySmall,
            modifier = Modifier.padding(top = 4.dp, bottom = 16.dp),
        )
        Column(
            modifier = Modifier
                .weight(1f)
                .verticalScroll(rememberScrollState()),
        ) {
            KyroCopy.faq.forEach { item ->
                FaqAccordion(item.question, item.answer)
                Spacer(Modifier.height(10.dp))
            }
            Spacer(Modifier.height(28.dp))
        }
    }
}

@Composable
private fun FaqAccordion(question: String, answer: String) {
    var open by remember { mutableStateOf(false) }
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .background(CqElev.copy(alpha = 0.7f))
            .border(1.dp, CqBorder, RoundedCornerShape(16.dp))
            .clickable { open = !open }
            .padding(16.dp),
    ) {
        Text(question, style = MaterialTheme.typography.titleMedium, color = CqText)
        AnimatedVisibility(
            visible = open,
            enter = fadeIn() + expandVertically(),
            exit = fadeOut() + shrinkVertically(),
        ) {
            Text(
                answer,
                style = MaterialTheme.typography.bodyMedium,
                color = CqMuted,
                modifier = Modifier.padding(top = 12.dp),
                lineHeight = 22.sp,
            )
        }
    }
}

/** Round luminous button with soft white “moths” / sparkles. */
@Composable
fun FaqSparkleButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Box(
        modifier = modifier
            .size(44.dp)
            .clip(CircleShape)
            .background(CqElev)
            .border(1.dp, CqText.copy(alpha = 0.16f), CircleShape)
            .clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Box(
            modifier = Modifier
                .align(Alignment.TopEnd)
                .padding(top = 9.dp, end = 11.dp)
                .size(3.dp)
                .clip(CircleShape)
                .background(CqText.copy(alpha = 0.85f)),
        )
        Box(
            modifier = Modifier
                .align(Alignment.CenterStart)
                .padding(start = 10.dp)
                .size(2.dp)
                .clip(CircleShape)
                .background(CqText.copy(alpha = 0.55f)),
        )
        Box(
            modifier = Modifier
                .align(Alignment.BottomEnd)
                .padding(bottom = 11.dp, end = 13.dp)
                .size(2.dp)
                .clip(CircleShape)
                .background(CqText.copy(alpha = 0.7f)),
        )
        Text(
            "?",
            color = CqText,
            style = MaterialTheme.typography.titleMedium,
        )
    }
}
