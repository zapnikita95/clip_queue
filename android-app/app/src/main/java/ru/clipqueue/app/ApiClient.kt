package ru.clipqueue.app

import io.ktor.client.HttpClient
import io.ktor.client.call.body
import io.ktor.client.engine.android.Android
import io.ktor.client.plugins.contentnegotiation.ContentNegotiation
import io.ktor.client.plugins.defaultRequest
import io.ktor.client.request.delete
import io.ktor.client.request.get
import io.ktor.client.request.header
import io.ktor.client.request.patch
import io.ktor.client.request.post
import io.ktor.client.request.setBody
import io.ktor.http.ContentType
import io.ktor.http.HttpHeaders
import io.ktor.http.contentType
import io.ktor.serialization.gson.gson
import ru.clipqueue.app.data.AuthResponse
import ru.clipqueue.app.data.CreateListResponse
import ru.clipqueue.app.data.CreateTagResponse
import ru.clipqueue.app.data.ListDetailResponse
import ru.clipqueue.app.data.ListsResponse
import ru.clipqueue.app.data.MeResponse
import ru.clipqueue.app.data.OkResponse
import ru.clipqueue.app.data.OpenResponse
import ru.clipqueue.app.data.RailResponse
import ru.clipqueue.app.data.SaveHistoryResponse
import ru.clipqueue.app.data.SaveResponse
import ru.clipqueue.app.data.SimilarResponse
import ru.clipqueue.app.data.SyncStartResponse
import ru.clipqueue.app.data.TagsResponse
import ru.clipqueue.app.data.VideoDetailResponse

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

    private suspend inline fun <reified T> get(path: String): T =
        client.get(path) { authHeaders().forEach { (k, v) -> header(k, v) } }.body()

    private suspend inline fun <reified T> post(path: String, body: Any = emptyMap<String, String>()): T =
        client.post(path) {
            authHeaders().forEach { (k, v) -> header(k, v) }
            setBody(body)
        }.body()

    private suspend inline fun <reified T> patch(path: String, body: Any): T =
        client.patch(path) {
            authHeaders().forEach { (k, v) -> header(k, v) }
            setBody(body)
        }.body()

    suspend fun me(): MeResponse = get("/api/me")

    suspend fun devLogin(): AuthResponse = post("/api/auth/dev-login")

    suspend fun saveVideo(url: String, source: String = "android_share"): SaveResponse =
        post(
            "/api/videos/save",
            mapOf(
                "url" to url,
                "source" to source,
                "apply_classification" to true,
                "status" to "queue",
            ),
        )

    suspend fun homeRail(railId: String): RailResponse = get("/api/home/rails/$railId")

    suspend fun lists(): ListsResponse = get("/api/lists")

    suspend fun listDetail(id: Int): ListDetailResponse = get("/api/lists/$id")

    suspend fun createList(title: String): CreateListResponse =
        post("/api/lists", mapOf("title" to title))

    suspend fun video(videoId: String): VideoDetailResponse =
        get("/api/videos/${java.net.URLEncoder.encode(videoId, "UTF-8")}")

    suspend fun similar(videoId: String): SimilarResponse =
        get("/api/videos/${java.net.URLEncoder.encode(videoId, "UTF-8")}/similar")

    suspend fun openVideo(videoId: String): OpenResponse =
        post("/api/videos/${java.net.URLEncoder.encode(videoId, "UTF-8")}/open")

    suspend fun patchLibrary(videoId: String, body: Map<String, Any?>): OkResponse =
        patch("/api/library/${java.net.URLEncoder.encode(videoId, "UTF-8")}", body)

    suspend fun deleteLibrary(videoId: String): OkResponse =
        client.delete("/api/library/${java.net.URLEncoder.encode(videoId, "UTF-8")}") {
            authHeaders().forEach { (k, v) -> header(k, v) }
        }.body()

    suspend fun tags(): TagsResponse = get("/api/tags")

    suspend fun createTag(name: String, emoji: String = ""): CreateTagResponse =
        post("/api/tags", mapOf("name" to name, "emoji" to emoji))

    suspend fun seedTags(): TagsResponse = post("/api/tags/seed-defaults")

    suspend fun startYoutubeSync(full: Boolean = false): SyncStartResponse =
        post("/api/youtube/sync", mapOf("full" to full))

    suspend fun saveHistory(limit: Int = 40): SaveHistoryResponse =
        get("/api/saves/history?limit=$limit")

    fun googleStartUrl(): String = "$baseUrl/api/auth/google/start?client=android"
}
