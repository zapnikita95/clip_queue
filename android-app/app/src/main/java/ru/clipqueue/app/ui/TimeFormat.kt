package ru.clipqueue.app.ui

import java.time.Instant
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

object TimeFormat {
    private val outFmt = DateTimeFormatter.ofPattern("d MMM yyyy, HH:mm", Locale("ru"))

    fun syncLocal(raw: String?): String {
        if (raw.isNullOrBlank()) return "ещё не было"
        val zone = ZoneId.systemDefault()
        val zdt = runCatching {
            OffsetDateTime.parse(raw).atZoneSameInstant(zone)
        }.recoverCatching {
            Instant.parse(raw).atZone(zone)
        }.recoverCatching {
            // "2026-08-03 16:18:00" / postgres without zone
            val cleaned = raw.trim().replace(" ", "T")
            val local = LocalDateTime.parse(cleaned.take(19))
            local.atZone(ZoneId.of("UTC")).withZoneSameInstant(zone)
        }.getOrNull()
        return zdt?.format(outFmt) ?: raw
    }
}
