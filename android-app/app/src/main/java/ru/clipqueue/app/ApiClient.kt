package ru.clipqueue.app

import io.ktor.client.HttpClient
import io.ktor.client.call.body
import io.ktor.client.engine.android.Android
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.plugins.defaultRequest
import io.ktor.client.request.get
import io.ktor.client.request.header
import io.ktor.client.request.post
import io.ktor.client.request.setBody
import io.ktor.client.statement.bodyAsText
import io.ktor.http.ContentType
import io.ktor.http.HttpHeaders
import io.ktor.http.contentType
import io.ktor.http.isSuccess
import io.ktor.serialization.gson.gson
import ru.clipqueue.app.data.AuthResponse
import ru.clipqueue.app.data.HomeShell
import ru.clipqueue.app.data.ListDetailResponse
import ru.clipqueue.app.data.ListsResponse
import ru.clipqueue.app.data.MeResponse
import ru.clipqueue.app.data.OpenResponse
import ru.clipqueue.app.data.RailResponse
import ru.clipqueue.app.data.SaveResponse
import ru.clipqueue.app.data.SyncStartResponse

class ApiClient(private val session: SessionStore) {
    val baseUrl: String = BuildConfig.API_BASE.trimEnd('/')

    private val client = HttpClient(Android) {
        expectSuccess = false
        install(ContentNegotiation) { gson() }
        defaultRequest {
            url(baseUrl)
            contentType(ContentType.Application.Json)
        }
    }

    private fun authHeaders(): Map<String, String> {
        val t = session.token ?: return emptyMap()
        return mapOf(HttpHeaders.Authorization to "Bearer $t")
    }

    suspend fun me(): MeResponse =
        client.get("/api/me") {
            authHeaders().forEach { (k, v) -> header(k, v) }
        }.body()

    suspend fun devLogin(): AuthResponse =
        client.post("/api/auth/dev-login") {
            setBody(emptyMap<String, String>())
        }.body()

    suspend fun saveVideo(url: String, source: String = "android_share"): SaveResponse =
        client.post("/api/videos/save") {
            authHeaders().forEach { (k, v) -> header(k, v) }
            setBody(
                mapOf(
                    "url" to url,
                    "source" to source,
                    "apply_classification" to true,
                    "status" to "queue",
                ),
            )
        }.body()

    suspend fun homeShell(): HomeShell =
        client.get("/api/home/shell") {
            authHeaders().forEach { (k, v) -> header(k, v) }
        }.body()

    suspend fun homeRail(railId: String): RailResponse =
        client.get("/api/home/rails/$railId") {
            authHeaders().forEach { (k, v) -> header(k, v) }
        }.body()

    suspend fun lists(): ListsResponse =
        client.get("/api/lists") {
            authHeaders().forEach { (k, v) -> header(k, v) }
        }.body()

    suspend fun listDetail(id: Int): ListDetailResponse =
        client.get("/api/lists/$id") {
            authHeaders().forEach { (k, v) -> header(k, v) }
        }.body()

    suspend fun openVideo(videoId: String): OpenResponse =
        client.post("/api/videos/$videoId/open") {
            authHeaders().forEach { (k, v) -> header(k, v) }
            setBody(emptyMap<String, String>())
        }.body()

    suspend fun startYoutubeSync(full: Boolean = false): SyncStartResponse =
        client.post("/api/youtube/sync") {
            authHeaders().forEach { (k, v) -> header(k, v) }
            setBody(mapOf("full" to full))
        }.body()

    fun googleStartUrl(): String = "$baseUrl/api/auth/google/start?client=android"

    suspend fun rawError(path: String): String {
        val r = client.get(path) {
            authHeaders().forEach { (k, v) -> header(k, v) }
        }
        return if (r.status.isSuccess()) "" else r.bodyAsText().take(200)
    }
}
