package ru.clipqueue.app.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.Typography
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import ru.clipqueue.app.R

val CqBg = Color(0xFF0A0A0C)
val CqElev = Color(0xFF121216)
val CqElev2 = Color(0xFF1A1A20)
val CqText = Color(0xFFF3F3F5)
val CqMuted = Color(0xFF8E8E98)
/** Luminous primary (Kyro) — not YouTube red as system accent */
val CqAccent = Color(0xFFF3F3F5)
val CqAccent2 = Color(0xFFC8C8D0)
val CqOnAccent = Color(0xFF0A0A0C)
val CqOk = Color(0xFF3DD68C)
val CqBorder = Color(0x14FFFFFF)
val CqWhisper = Color(0x88FF4848)

val KyroFont = FontFamily(
    Font(R.font.outfit_light, FontWeight.Light),
    Font(R.font.outfit_regular, FontWeight.Normal),
    Font(R.font.outfit_medium, FontWeight.Medium),
    Font(R.font.outfit_semibold, FontWeight.SemiBold),
)

private val DarkColors = darkColorScheme(
    primary = CqAccent,
    onPrimary = CqOnAccent,
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
        fontFamily = KyroFont,
        fontWeight = FontWeight.Medium,
        fontSize = 34.sp,
        letterSpacing = (-0.8).sp,
        color = CqText,
    ),
    headlineMedium = TextStyle(
        fontFamily = KyroFont,
        fontWeight = FontWeight.Medium,
        fontSize = 24.sp,
        letterSpacing = (-0.5).sp,
        color = CqText,
    ),
    titleLarge = TextStyle(
        fontFamily = KyroFont,
        fontWeight = FontWeight.Medium,
        fontSize = 22.sp,
        letterSpacing = (-0.4).sp,
        color = CqText,
    ),
    titleMedium = TextStyle(
        fontFamily = KyroFont,
        fontWeight = FontWeight.Medium,
        fontSize = 15.sp,
        letterSpacing = (-0.2).sp,
        color = CqText,
    ),
    bodyMedium = TextStyle(
        fontFamily = KyroFont,
        fontWeight = FontWeight.Normal,
        fontSize = 14.sp,
        color = CqText,
        lineHeight = 20.sp,
    ),
    bodyLarge = TextStyle(
        fontFamily = KyroFont,
        fontWeight = FontWeight.Light,
        fontSize = 15.sp,
        color = CqMuted,
        lineHeight = 22.sp,
    ),
    bodySmall = TextStyle(
        fontFamily = KyroFont,
        fontWeight = FontWeight.Normal,
        fontSize = 12.sp,
        color = CqMuted,
    ),
    labelSmall = TextStyle(
        fontFamily = KyroFont,
        fontWeight = FontWeight.Medium,
        fontSize = 11.sp,
        letterSpacing = 0.8.sp,
        color = CqMuted,
    ),
)

/** Home brand wordmark — matches designs/kyro `.brand-row .ky` */
val KyroBrandStyle = TextStyle(
    fontFamily = KyroFont,
    fontWeight = FontWeight.Medium,
    fontSize = 18.4.sp, // ~1.15rem
    letterSpacing = (-0.04 * 18.4).sp,
    color = CqText,
)

@Composable
fun ClipQueueTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = DarkColors,
        typography = CqTypography,
        content = content,
    )
}
