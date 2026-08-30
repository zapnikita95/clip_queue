package ru.clipqueue.app.push

/** Parse progress strings for watch-session notification RemoteInput. */
object ProgressParse {
    private val pct = Regex("""^\s*(\d{1,3})\s*%\s*$""")
    private val sepHms = Regex(
        """^\s*(?:(\d{1,3})\s*[:.'\-]\s*)?(\d{1,3})\s*[:.'\-]\s*(\d{1,3})\s*"?\s*$""",
    )
    private val unit = Regex(
        """(\d+(?:[.,]\d+)?)\s*(час(?:а|ов)?|ч|hours?|hrs?|h|минут(?:а|ы)?|мин|м|minutes?|mins?|m|секунд(?:а|ы)?|сек|с|seconds?|secs?|s)(?![a-zа-яё])""",
        setOf(RegexOption.IGNORE_CASE),
    )
    private val mThenS = Regex(
        """^\s*(\d+)\s*(?:м|мин|m|min)\s*(\d+)\s*(?:с|сек|s|sec)?\s*$""",
        RegexOption.IGNORE_CASE,
    )
    private val bare = Regex("""^\s*(\d{1,5})\s*$""")

    /** Returns seconds, or null if blank/invalid. */
    fun parse(raw: String?, durationSec: Int? = null): Int? {
        var s = raw?.trim()?.lowercase() ?: return null
        if (s.isEmpty()) return null
        s = s
            .replace(',', '.')
            .replace('′', '\'')
            .replace('″', '"')
            .replace('’', '\'')
            .replace('`', '\'')
            .replace('´', '\'')
            .replace('—', '-')
            .replace('–', '-')
            .replace(Regex("""\s+"""), " ")

        pct.matchEntire(s)?.let { m ->
            val p = m.groupValues[1].toInt().coerceIn(0, 100)
            val dur = durationSec ?: return null
            if (dur <= 0) return null
            return (dur * p) / 100
        }

        sepHms.matchEntire(s)?.let { m ->
            val a = m.groupValues[1]
            val b = m.groupValues[2].toInt()
            val c = m.groupValues[3].toInt()
            val h = if (a.isBlank()) 0 else a.toInt()
            val mm = b
            val ss = c
            if (mm > 59 || ss > 59) {
                if (h == 0 && mm <= 999 && ss <= 59) return mm * 60 + ss
                return null
            }
            return h * 3600 + mm * 60 + ss
        }

        var total = 0
        var found = false
        for (um in unit.findAll(s)) {
            found = true
            val n = um.groupValues[1].replace(',', '.').toDoubleOrNull() ?: continue
            val u = um.groupValues[2].lowercase()
            total += when {
                u.startsWith("час") || u.startsWith("hour") || u.startsWith("hr") ||
                    u == "h" || u == "ч" -> (n * 3600).toInt()
                u.startsWith("мин") || u.startsWith("min") || u == "m" || u == "м" ->
                    (n * 60).toInt()
                else -> n.toInt()
            }
        }
        if (found) return total.coerceAtLeast(0)

        mThenS.matchEntire(s)?.let { m ->
            return m.groupValues[1].toInt() * 60 + m.groupValues[2].toInt()
        }

        bare.matchEntire(s)?.let { m ->
            val n = m.groupValues[1].toInt()
            return if (n <= 600 && (durationSec == null || n * 60 <= durationSec + 120)) {
                n * 60
            } else {
                n
            }
        }
        return null
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
