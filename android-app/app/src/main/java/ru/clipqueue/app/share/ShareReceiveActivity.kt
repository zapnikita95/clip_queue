package ru.clipqueue.app.share

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.widget.Toast
import org.json.JSONArray
import org.json.JSONObject
import ru.clipqueue.app.BuildConfig
import ru.clipqueue.app.MainActivity
import ru.clipqueue.app.R
import ru.clipqueue.app.SaveHistoryStore
import ru.clipqueue.app.SessionStore
import ru.clipqueue.app.data.ClassifiedInto
import ru.clipqueue.app.data.ListRef
import ru.clipqueue.app.data.SaveEvent
import ru.clipqueue.app.data.TagDto
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.Executors
import java.util.regex.Pattern

/**
 * Headless share target: quick save (no wait for classify), toast, finish.
 * Classification + push happen on the backend.
 */
class ShareReceiveActivity : Activity() {
    private val executor = Executors.newSingleThreadExecutor()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        handle(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handle(intent)
    }

    private fun handle(intent: Intent?) {
        val text = buildString {
            intent?.getStringExtra(Intent.EXTRA_SUBJECT)?.let { append(it).append('\n') }
            intent?.getStringExtra(Intent.EXTRA_TEXT)?.let { append(it) }
            if (intent?.action == Intent.ACTION_SEND_MULTIPLE) {
                intent.getStringArrayListExtra(Intent.EXTRA_TEXT)?.forEach {
                    append('\n').append(it)
                }
            }
        }.trim()

        val url = extractYoutubeUrl(text)
        if (url == null) {
            toast(getString(R.string.share_no_url))
            finish()
            return
        }

        val token = SessionStore.readMirrorToken(this)
        if (token.isNullOrBlank()) {
            toast(getString(R.string.share_need_login))
            startActivity(
                Intent(this, MainActivity::class.java).apply {
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
                },
            )
            finish()
            return
        }

        executor.execute {
            val result = saveOnBackend(token, url)
            runOnUiThread {
                when {
                    result == null -> toast(getString(R.string.share_error))
                    else -> {
                        SaveHistoryStore(this).add(result)
                        toast(getString(R.string.share_saved))
                    }
                }
                finish()
            }
        }
    }

    private fun toast(msg: String) {
        Toast.makeText(applicationContext, msg, Toast.LENGTH_SHORT).show()
    }

    private fun saveOnBackend(token: String, videoUrl: String): SaveEvent? {
        return try {
            val endpoint = URL("${BuildConfig.API_BASE.trimEnd('/')}/api/videos/save")
            val conn = (endpoint.openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = 10_000
                readTimeout = 15_000
                doOutput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
                setRequestProperty("Authorization", "Bearer $token")
            }
            val body = JSONObject()
                .put("url", videoUrl)
                .put("source", "android_share")
                .put("apply_classification", true)
                .put("classify_async", true)
                .put("status", "queue")
                .toString()
            OutputStreamWriter(conn.outputStream, Charsets.UTF_8).use { it.write(body) }
            val code = conn.responseCode
            val stream = if (code in 200..299) conn.inputStream else conn.errorStream
            val raw = stream?.bufferedReader()?.readText().orEmpty()
            if (code !in 200..299) return null
            val json = JSONObject(if (raw.isBlank()) "{}" else raw)
            if (!json.optBoolean("ok", true)) return null
            val item = json.optJSONObject("item")
            val now = SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.US).format(Date())
            SaveEvent(
                video_id = item?.optString("video_id")?.ifBlank { null }
                    ?: json.optString("video_id").ifBlank { null }
                    ?: extractIdFromUrl(videoUrl),
                title = item?.optString("title") ?: json.optString("title"),
                channel_title = item?.optString("channel_title"),
                thumb_url = item?.optString("thumb_url"),
                source = "android_share",
                classified_into = parseClassified(json.optJSONArray("classified_into")),
                in_lists = parseLists(json.optJSONArray("in_lists")),
                tags = parseTags(json.optJSONArray("tags") ?: item?.optJSONArray("user_tags")),
                classify_engine = json.optString("classify_engine"),
                classify_reason = json.optString("classify_reason"),
                created_at = now,
            )
        } catch (_: Exception) {
            null
        }
    }

    private fun parseClassified(arr: JSONArray?): List<ClassifiedInto> {
        if (arr == null) return emptyList()
        return (0 until arr.length()).map { i ->
            val o = arr.getJSONObject(i)
            ClassifiedInto(
                list_id = if (o.has("list_id") && !o.isNull("list_id")) o.optInt("list_id") else null,
                list_title = o.optString("list_title"),
            )
        }
    }

    private fun parseLists(arr: JSONArray?): List<ListRef> {
        if (arr == null) return emptyList()
        return (0 until arr.length()).map { i ->
            val o = arr.getJSONObject(i)
            ListRef(
                id = if (o.has("id") && !o.isNull("id")) o.optInt("id") else null,
                title = o.optString("title"),
            )
        }
    }

    private fun parseTags(arr: JSONArray?): List<TagDto> {
        if (arr == null) return emptyList()
        return (0 until arr.length()).map { i ->
            val o = arr.getJSONObject(i)
            TagDto(
                id = if (o.has("id") && !o.isNull("id")) o.optInt("id") else null,
                name = o.optString("name"),
                emoji = o.optString("emoji"),
            )
        }
    }

    private fun extractIdFromUrl(url: String): String? {
        val m = Pattern.compile("[?&]v=([a-zA-Z0-9_-]{11})|youtu\\.be/([a-zA-Z0-9_-]{11})|shorts/([a-zA-Z0-9_-]{11})")
            .matcher(url)
        if (!m.find()) return null
        return m.group(1) ?: m.group(2) ?: m.group(3)
    }

    companion object {
        private val YT = Pattern.compile(
            "(https?://(?:www\\.)?(?:youtube\\.com/watch\\S*|youtu\\.be/\\S+|youtube\\.com/shorts/\\S+|m\\.youtube\\.com/\\S+))",
            Pattern.CASE_INSENSITIVE,
        )

        fun extractYoutubeUrl(text: String): String? {
            if (text.isBlank()) return null
            val m = YT.matcher(text)
            if (m.find()) return m.group(1)?.trim()?.trimEnd(')', ',', '.', '"', '\'')
            val id = Regex("^[a-zA-Z0-9_-]{11}$").find(text.trim())?.value
            return id?.let { "https://www.youtube.com/watch?v=$it" }
        }
    }
}
