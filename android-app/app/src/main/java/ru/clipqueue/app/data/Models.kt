package ru.clipqueue.app.data

data class MeResponse(
    val ok: Boolean? = null,
    val user: UserDto? = null,
    val youtube_connected: Boolean? = null,
    val library_count: Int? = null,
    val last_youtube_sync: LastSyncDto? = null,
    val google_oauth_configured: Boolean? = null,
    val error: String? = null,
)

data class LastSyncDto(
    val status: String? = null,
    val at: String? = null,
)

data class UserDto(
    val id: Int? = null,
    val email: String? = null,
    val name: String? = null,
)

data class AuthResponse(
    val ok: Boolean? = null,
    val token: String? = null,
    val user: UserDto? = null,
    val error: String? = null,
)

data class SaveResponse(
    val ok: Boolean? = null,
    val error: String? = null,
    val item: VideoCard? = null,
    val classified_into: List<ClassifiedInto>? = null,
    val in_lists: List<ListRef>? = null,
    val tags: List<TagDto>? = null,
    val classify_engine: String? = null,
    val classify_reason: String? = null,
)

data class ClassifiedInto(
    val list_id: Int? = null,
    val list_title: String? = null,
)

data class ListRef(
    val id: Int? = null,
    val title: String? = null,
)

data class SaveHistoryResponse(
    val ok: Boolean? = null,
    val events: List<SaveEvent>? = null,
    val error: String? = null,
)

data class SaveEvent(
    val id: Int? = null,
    val video_id: String? = null,
    val title: String? = null,
    val channel_title: String? = null,
    val thumb_url: String? = null,
    val source: String? = null,
    val classified_into: List<ClassifiedInto>? = null,
    val tags: List<TagDto>? = null,
    val in_lists: List<ListRef>? = null,
    val classify_engine: String? = null,
    val classify_reason: String? = null,
    val created_at: String? = null,
)

data class HomeShell(
    val ok: Boolean? = null,
    val rails: List<RailMeta>? = null,
    val error: String? = null,
)

data class RailMeta(
    val id: String? = null,
    val title: String? = null,
)

data class RailResponse(
    val ok: Boolean? = null,
    val items: List<VideoCard>? = null,
    val error: String? = null,
)

data class NowSlotDto(
    val id: String? = null,
    val label: String? = null,
)

data class NowMoodDto(
    val id: String? = null,
    val label: String? = null,
    val hint: String? = null,
)

data class NowResponse(
    val ok: Boolean? = null,
    val slot: String? = null,
    val slot_label: String? = null,
    val mood: String? = null,
    val mood_label: String? = null,
    val picks: List<VideoCard>? = null,
    val started: List<VideoCard>? = null,
    val suggestions: List<VideoCard>? = null,
    val slots: List<NowSlotDto>? = null,
    val moods: List<NowMoodDto>? = null,
    val error: String? = null,
)

data class LightPlanResponse(
    val ok: Boolean? = null,
    val tonight: List<VideoCard>? = null,
    val week: List<VideoCard>? = null,
    val error: String? = null,
)

data class InboxOnboardingResponse(
    val ok: Boolean? = null,
    val has_inbox: Boolean? = null,
    val hint: String? = null,
    val onboarding_done: Boolean? = null,
    val error: String? = null,
)

data class MetricsSummaryResponse(
    val ok: Boolean? = null,
    val weekly_planned_watches: Int? = null,
    val surface_active_days: Int? = null,
    val depth_themed_pct: Double? = null,
    val error: String? = null,
)

data class VideoCard(
    val video_id: String? = null,
    val title: String? = null,
    val channel_title: String? = null,
    val thumb_url: String? = null,
    val duration_sec: Int? = null,
    val duration_label: String? = null,
    val status: String? = null,
    val interest: Int? = null,
    val watch_url: String? = null,
    val description: String? = null,
    val note: String? = null,
    val reason: String? = null,
    val user_tags: List<TagDto>? = null,
    val in_lists: List<ListRef>? = null,
)

data class VideoDetailResponse(
    val ok: Boolean? = null,
    val item: VideoCard? = null,
    val error: String? = null,
)

data class OkResponse(
    val ok: Boolean? = null,
    val error: String? = null,
)

data class ListsResponse(
    val ok: Boolean? = null,
    val lists: List<ListCard>? = null,
    val error: String? = null,
)

data class CoverDto(
    val thumb_url: String? = null,
    val title: String? = null,
)

data class ListCard(
    val id: Int? = null,
    val title: String? = null,
    val count: Int? = null,
    val covers: List<CoverDto>? = null,
    val hidden_from_home: Boolean? = null,
)

data class ListDetailResponse(
    val ok: Boolean? = null,
    val list: ListCard? = null,
    val items: List<VideoCard>? = null,
    val error: String? = null,
)

data class CreateListResponse(
    val ok: Boolean? = null,
    val list: ListCard? = null,
    val error: String? = null,
)

data class TagsResponse(
    val ok: Boolean? = null,
    val tags: List<TagDto>? = null,
    val error: String? = null,
)

data class TagDto(
    val id: Int? = null,
    val name: String? = null,
    val emoji: String? = null,
    val video_count: Int? = null,
)

data class CreateTagResponse(
    val ok: Boolean? = null,
    val tag: TagDto? = null,
    val error: String? = null,
)

data class OpenResponse(
    val ok: Boolean? = null,
    val watch_url: String? = null,
    val error: String? = null,
)

data class SyncStartResponse(
    val ok: Boolean? = null,
    val job: Map<String, Any?>? = null,
    val error: String? = null,
)

data class SimilarResponse(
    val ok: Boolean? = null,
    val items: List<VideoCard>? = null,
)
