package ru.clipqueue.app.push

/**
 * Parse progress for watch-session RemoteInput.
 * Accepts almost any human form: 20 сек, 2м3с, 12:34, 25мин, 90s, …
 */
object ProgressParse {
    private val digitsFirst = Regex("""^\s*(\d+(?:[.,]\d+)?)(.*)$""", RegexOption.DOT_MATCHES_ALL)

    /** Returns seconds, or null if blank/invalid. */
    fun parse(raw: String?, durationSec: Int? = null): Int? {
        var s = normalize(raw) ?: return null

        // percent
        Regex("""^(\d{1,3})\s*%$""").matchEntire(s)?.let { m ->
            val p = m.groupValues[1].toInt().coerceIn(0, 100)
            val dur = durationSec ?: return null
            if (dur <= 0) return null
            return (dur * p) / 100
        }

        // h:m:s / m:s with : . ' -
        Regex(
            """^(?:(\d{1,3})\s*[:.\'\-]\s*)?(\d{1,3})\s*[:.\'\-]\s*(\d{1,3})\s*"?$""",
        ).matchEntire(s)?.let { m ->
            val a = m.groupValues[1]
            val b = m.groupValues[2].toInt()
            val c = m.groupValues[3].toInt()
            val h = if (a.isBlank()) 0 else a.toInt()
            if (b > 59 || c > 59) {
                if (h == 0 && b <= 999 && c <= 59) return b * 60 + c
                return null
            }
            return h * 3600 + b * 60 + c
        }

        // 2м3с / 2m3s / 2м3 (no trailing unit on seconds)
        Regex(
            """^(\d+)\s*(?:час(?:а|ов)?|ч|h|hours?|hrs?)\s*(\d+)\s*(?:минут(?:а|ы)?|мин|м|m|min(?:ute)?s?)\s*(?:(\d+)\s*(?:секунд(?:а|ы)?|сек|с|s|sec(?:ond)?s?)?)?$""",
            RegexOption.IGNORE_CASE,
        ).matchEntire(s)?.let { m ->
            val h = m.groupValues[1].toInt()
            val mm = m.groupValues[2].toInt()
            val ss = m.groupValues[3].toIntOrNull() ?: 0
            return h * 3600 + mm * 60 + ss
        }
        Regex(
            """^(\d+)\s*(?:минут(?:а|ы)?|мин|м|m|min(?:ute)?s?)\s*(\d+)\s*(?:секунд(?:а|ы)?|сек|с|s|sec(?:ond)?s?)?$""",
            RegexOption.IGNORE_CASE,
        ).matchEntire(s)?.let { m ->
            return m.groupValues[1].toInt() * 60 + m.groupValues[2].toInt()
        }

        // Single number + unit (ORDER MATTERS: seconds before minutes before hours)
        digitsFirst.matchEntire(s)?.let { m ->
            val n = m.groupValues[1].replace(',', '.').toDoubleOrNull() ?: return@let
            val unit = m.groupValues[2].trim()
            if (unit.isEmpty()) {
                val ni = n.toInt()
                return if (ni <= 600 && (durationSec == null || ni * 60 <= durationSec + 120)) {
                    ni * 60
                } else {
                    ni
                }
            }
            val u = unit.lowercase()
            // seconds — check FIRST (сек / sec / с / s)
            if (isSecondsUnit(u)) return n.toInt().coerceAtLeast(0)
            if (isMinutesUnit(u)) return (n * 60).toInt()
            if (isHoursUnit(u)) return (n * 3600).toInt()
        }

        // Multi-unit scan: 1ч 2м 3с
        var total = 0
        var found = false
        val multi = Regex(
            """(\d+(?:[.,]\d+)?)\s*(час(?:а|ов)?|ч|hours?|hrs?|h|минут(?:а|ы)?|мин|м|minutes?|mins?|m|секунд(?:а|ы)?|сек|с|seconds?|secs?|s)\b""",
            setOf(RegexOption.IGNORE_CASE),
        )
        for (um in multi.findAll(s)) {
            found = true
            val n = um.groupValues[1].replace(',', '.').toDoubleOrNull() ?: continue
            val u = um.groupValues[2]
            total += when {
                isHoursUnit(u) -> (n * 3600).toInt()
                isMinutesUnit(u) -> (n * 60).toInt()
                else -> n.toInt()
            }
        }
        if (found) return total.coerceAtLeast(0)

        return null
    }

    private fun isSecondsUnit(u: String): Boolean {
        val x = u.lowercase().trim()
        return x == "с" || x == "c" || x == "s" ||
            x.startsWith("сек") || x.startsWith("sec") ||
            x == "секунд" || x == "секунда" || x == "секунды" ||
            x == "second" || x == "seconds" || x == "secs"
    }

    private fun isMinutesUnit(u: String): Boolean {
        val x = u.lowercase().trim()
        if (isSecondsUnit(x)) return false
        return x == "м" || x == "m" ||
            x.startsWith("мин") || x.startsWith("min") ||
            x == "минута" || x == "минуты" || x == "минут"
    }

    private fun isHoursUnit(u: String): Boolean {
        val x = u.lowercase().trim()
        return x == "ч" || x == "h" ||
            x.startsWith("час") || x.startsWith("hour") || x.startsWith("hr")
    }

    private fun normalize(raw: String?): String? {
        if (raw == null) return null
        var s = raw.trim()
        if (s.isEmpty()) return null
        // NBSP / thin spaces / BOM
        s = s
            .replace('\u00A0', ' ')
            .replace('\u202F', ' ')
            .replace('\u2007', ' ')
            .replace('\uFEFF', ' ')
            .replace(',', '.')
            .replace('′', '\'')
            .replace('″', '"')
            .replace('’', '\'')
            .replace('`', '\'')
            .replace('´', '\'')
            .replace('—', '-')
            .replace('–', '-')
            .replace(Regex("""\s+"""), " ")
            .trim()
            .lowercase()
        return s.ifEmpty { null }
    }

    fun format(sec: Int?): String? {
        if (sec == null || sec < 0) return null
        val h = sec / 3600
        val rem = sec % 3600
        val m = rem / 60
        val s = rem % 60
        return if (h > 0) "%d:%02d:%02d".format(h, m, s) else "%d:%02d".format(m, s)
    }

    /** Append or replace YouTube start offset (?t= / &t=). */
    fun withStartOffset(url: String, progressSec: Int?): String {
        val t = progressSec ?: return url
        if (t <= 0) return url
        val base = url.replace(Regex("""([?&])t=\d+s?"""), "").trimEnd('?', '&')
        val sep = if (base.contains('?')) "&" else "?"
        return "${base}${sep}t=$t"
    }
}
