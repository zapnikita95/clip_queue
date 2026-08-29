package ru.clipqueue.app.push

/** Parse progress strings for watch-session notification RemoteInput. */
object ProgressParse {
    private val hm = Regex("""^\s*(?:(\d{1,2})\s*[:.]\s*)?(\d{1,2})\s*[:.]\s*(\d{1,2})\s*$""")
    private val min = Regex("""^\s*(\d{1,4})\s*(?:м|мин|min|m)?\s*$""", RegexOption.IGNORE_CASE)
    private val pct = Regex("""^\s*(\d{1,3})\s*%\s*$""")

    /** Returns seconds, or null if blank/invalid. */
    fun parse(raw: String?, durationSec: Int? = null): Int? {
        val s = raw?.trim()?.replace(',', '.') ?: return null
        if (s.isEmpty()) return null
        pct.matchEntire(s)?.let { m ->
            val p = m.groupValues[1].toInt().coerceIn(0, 100)
            val dur = durationSec ?: return null
            if (dur <= 0) return null
            return (dur * p) / 100
        }
        hm.matchEntire(s)?.let { m ->
            val h = m.groupValues[1].ifBlank { "0" }.toInt()
            val mm = m.groupValues[2].toInt()
            val ss = m.groupValues[3].toInt()
            if (mm > 59 || ss > 59) return null
            return h * 3600 + mm * 60 + ss
        }
        min.matchEntire(s)?.let { m ->
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
}
