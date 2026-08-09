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
import ru.clipqueue.app.data.NowResponse
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
                "classify_async" to (source == "android_share"),
                "status" to "queue",
            ),
        )

    suspend fun registerDevice(token: String, platform: String = "android"): OkResponse =
        post(
            "/api/devices/register",
            mapOf("token" to token, "platform" to platform),
        )

    suspend fun unregisterDevice(token: String): OkResponse =
        client.delete("/api/devices/register") {
            authHeaders().forEach { (k, v) -> header(k, v) }
            setBody(mapOf("token" to token))
        }.body()

    suspend fun homeRail(railId: String): RailResponse = get("/api/home/rails/$railId")

    suspend fun homeNow(slot: String = "any", mood: String = "", limit: Int = 6): NowResponse {
        val qs = buildString {
            append("slot=${java.net.URLEncoder.encode(slot, "UTF-8")}&limit=$limit")
            if (mood.isNotBlank()) append("&mood=${java.net.URLEncoder.encode(mood, "UTF-8")}")
        }
        return get("/api/home/now?$qs")
    }

    suspend fun lists(tagId: Int? = null, forHome: Boolean = false): ListsResponse {
        val qs = buildString {
            val parts = mutableListOf<String>()
            if (tagId != null && tagId > 0) parts += "tag_id=$tagId"
            if (forHome) parts += "for_home=1"
            if (parts.isNotEmpty()) append("?").append(parts.joinToString("&"))
        }
        return get("/api/lists$qs")
    }

    suspend fun listDetail(id: Int): ListDetailResponse = get("/api/lists/$id")

    suspend fun createList(title: String): CreateListResponse =
        post("/api/lists", mapOf("title" to title))

    suspend fun patchList(listId: Int, body: Map<String, Any?>): OkResponse =
        patch("/api/lists/$listId", body)

    suspend fun deleteList(listId: Int): OkResponse =
        client.delete("/api/lists/$listId") {
            authHeaders().forEach { (k, v) -> header(k, v) }
        }.body()

    suspend fun hideListFromHome(listId: Int, hidden: Boolean = true): OkResponse =
        patchList(listId, mapOf("hidden_from_home" to hidden))

    suspend fun reorderLists(order: List<Int>): OkResponse =
        post("/api/lists/reorder", mapOf("order" to order))

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

    suspend fun setInterest(videoId: String, interest: Int): OkResponse =
        post(
            "/api/library/${java.net.URLEncoder.encode(videoId, "UTF-8")}/interest",
            mapOf("interest" to interest),
        )

    suspend fun tagVideo(videoId: String, tagId: Int): OkResponse =
        post(
            "/api/videos/${java.net.URLEncoder.encode(videoId, "UTF-8")}/tags",
            mapOf("tag_id" to tagId),
        )

    suspend fun untagVideo(videoId: String, tagId: Int): OkResponse =
        client.delete("/api/videos/${java.net.URLEncoder.encode(videoId, "UTF-8")}/tags/$tagId") {
            authHeaders().forEach { (k, v) -> header(k, v) }
        }.body()

    suspend fun addToList(listId: Int, videoId: String): OkResponse =
        post("/api/lists/$listId/items", mapOf("video_id" to videoId))

    suspend fun removeFromList(listId: Int, videoId: String): OkResponse =
        client.delete("/api/lists/$listId/items/${java.net.URLEncoder.encode(videoId, "UTF-8")}") {
            authHeaders().forEach { (k, v) -> header(k, v) }
        }.body()

    suspend fun tags(onlyUsed: Boolean = true): TagsResponse =
        get("/api/tags?used=${if (onlyUsed) "1" else "0"}")

    suspend fun createTag(name: String, emoji: String = ""): CreateTagResponse =
        post("/api/tags", mapOf("name" to name, "emoji" to emoji))

    suspend fun seedTags(): TagsResponse = post("/api/tags/seed-defaults")

    suspend fun startYoutubeSync(full: Boolean = false): SyncStartResponse =
        post("/api/youtube/sync", mapOf("full" to full))

    suspend fun saveHistory(limit: Int = 40): SaveHistoryResponse =
        get("/api/saves/history?limit=$limit")

    suspend fun library(
        status: String = "queue",
        tagId: Int? = null,
        kind: String = "all",
        limit: Int = 60,
    ): RailResponse {
        val qs = buildString {
            append("status=$status&kind=$kind&limit=$limit")
            if (tagId != null && tagId > 0) append("&tag_id=$tagId")
        }
        return get("/api/library?$qs")
    }

    suspend fun startClassifyPending(limit: Int = 200): OkResponse =
        post("/api/organize/classify-pending", mapOf("limit" to limit, "use_llm" to true))

    suspend fun uploadTakeout(jsonBody: String): OkResponse {
        return client.post("/api/youtube/takeout") {
            authHeaders().forEach { (k, v) -> header(k, v) }
            setBody(io.ktor.http.content.TextContent(jsonBody, ContentType.Application.Json))
        }.body()
    }

    fun googleStartUrl(): String = "$baseUrl/api/auth/google/start?client=android"
}
