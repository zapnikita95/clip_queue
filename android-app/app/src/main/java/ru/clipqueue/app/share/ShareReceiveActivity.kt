package ru.clipqueue.app.share

import android.app.Activity
import android.content.Intent
import android.os.Bundle
import android.widget.Toast
import org.json.JSONObject
import ru.clipqueue.app.BuildConfig
import ru.clipqueue.app.MainActivity
import ru.clipqueue.app.R
import ru.clipqueue.app.SessionStore
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors
import java.util.regex.Pattern

/**
 * Headless share target: save YouTube URL on backend, toast, finish.
 * Does not launch Compose UI.
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
            toast(R.string.share_no_url)
            finish()
            return
        }

        val token = SessionStore.readMirrorToken(this)
        if (token.isNullOrBlank()) {
            toast(R.string.share_need_login)
            startActivity(
                Intent(this, MainActivity::class.java).apply {
                    addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
                },
            )
            finish()
            return
        }

        executor.execute {
            val ok = saveOnBackend(token, url)
            runOnUiThread {
                toast(if (ok) R.string.share_saved else R.string.share_error)
                finish()
            }
        }
    }

    private fun toast(res: Int) {
        Toast.makeText(applicationContext, res, Toast.LENGTH_SHORT).show()
    }

    private fun saveOnBackend(token: String, videoUrl: String): Boolean {
        return try {
            val endpoint = URL("${BuildConfig.API_BASE.trimEnd('/')}/api/videos/save")
            val conn = (endpoint.openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                connectTimeout = 20_000
                readTimeout = 30_000
                doOutput = true
                setRequestProperty("Content-Type", "application/json; charset=utf-8")
                setRequestProperty("Authorization", "Bearer $token")
            }
            val body = JSONObject()
                .put("url", videoUrl)
                .put("source", "android_share")
                .put("apply_classification", true)
                .put("status", "queue")
                .toString()
            OutputStreamWriter(conn.outputStream, Charsets.UTF_8).use { it.write(body) }
            val code = conn.responseCode
            val stream = if (code in 200..299) conn.inputStream else conn.errorStream
            val raw = stream?.bufferedReader()?.readText().orEmpty()
            if (code !in 200..299) return false
            val json = JSONObject(if (raw.isBlank()) "{}" else raw)
            json.optBoolean("ok", code in 200..299)
        } catch (_: Exception) {
            false
        }
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
            // bare video id
            val id = Regex("^[a-zA-Z0-9_-]{11}$").find(text.trim())?.value
            return id?.let { "https://www.youtube.com/watch?v=$it" }
        }
    }
}
