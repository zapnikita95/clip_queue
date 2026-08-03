package ru.clipqueue.app.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.Typography
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

val CqBg = Color(0xFF0B0B0D)
val CqElev = Color(0xFF141418)
val CqElev2 = Color(0xFF1C1C22)
val CqText = Color(0xFFF2F2F4)
val CqMuted = Color(0xFF8A8A96)
val CqAccent = Color(0xFFFF3B30)
val CqAccent2 = Color(0xFFFF7A45)
val CqOk = Color(0xFF3DD68C)
val CqBorder = Color(0x1AFFFFFF)

private val DarkColors = darkColorScheme(
    primary = CqAccent,
    onPrimary = Color.White,
    secondary = CqAccent2,
    background = CqBg,
    onBackground = CqText,
    surface = CqElev,
    onSurface = CqText,
    surfaceVariant = CqElev2,
    onSurfaceVariant = CqMuted,
    outline = CqBorder,
)

private val CqTypography = Typography(
    displayLarge = TextStyle(
        fontFamily = FontFamily.Serif,
        fontWeight = FontWeight.Bold,
        fontSize = 34.sp,
        letterSpacing = (-0.5).sp,
        color = CqText,
    ),
    headlineMedium = TextStyle(
        fontFamily = FontFamily.Serif,
        fontWeight = FontWeight.SemiBold,
        fontSize = 24.sp,
        letterSpacing = (-0.3).sp,
        color = CqText,
    ),
    titleLarge = TextStyle(
        fontFamily = FontFamily.Serif,
        fontWeight = FontWeight.Bold,
        fontSize = 22.sp,
        color = CqText,
    ),
    titleMedium = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.Bold,
        fontSize = 15.sp,
        color = CqText,
    ),
    bodyMedium = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.Normal,
        fontSize = 14.sp,
        color = CqText,
        lineHeight = 20.sp,
    ),
    bodySmall = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.Normal,
        fontSize = 12.sp,
        color = CqMuted,
    ),
    labelSmall = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.Medium,
        fontSize = 11.sp,
        letterSpacing = 0.8.sp,
        color = CqMuted,
    ),
)

@Composable
fun ClipQueueTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = DarkColors,
        typography = CqTypography,
        content = content,
    )
}
