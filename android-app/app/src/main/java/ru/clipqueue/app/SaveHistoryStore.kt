package ru.clipqueue.app

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import ru.clipqueue.app.data.ClassifiedInto
import ru.clipqueue.app.data.ListRef
import ru.clipqueue.app.data.SaveEvent
import ru.clipqueue.app.data.TagDto

/** Local mirror of recent saves for offline debug (share target writes here). */
class SaveHistoryStore(context: Context) {
    private val prefs = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun add(event: SaveEvent) {
        val arr = JSONArray(prefs.getString(KEY, "[]") ?: "[]")
        val obj = JSONObject()
            .put("video_id", event.video_id)
            .put("title", event.title)
            .put("channel_title", event.channel_title)
            .put("thumb_url", event.thumb_url)
            .put("source", event.source)
            .put("classify_engine", event.classify_engine)
            .put("classify_reason", event.classify_reason)
            .put("created_at", event.created_at)
            .put("classified_into", JSONArray().apply {
                event.classified_into.orEmpty().forEach { c ->
                    put(JSONObject().put("list_id", c.list_id).put("list_title", c.list_title))
                }
            })
            .put("in_lists", JSONArray().apply {
                event.in_lists.orEmpty().forEach { l ->
                    put(JSONObject().put("id", l.id).put("title", l.title))
                }
            })
            .put("tags", JSONArray().apply {
                event.tags.orEmpty().forEach { t ->
                    put(JSONObject().put("id", t.id).put("name", t.name).put("emoji", t.emoji))
                }
            })
        val next = JSONArray()
        next.put(obj)
        for (i in 0 until minOf(arr.length(), MAX - 1)) next.put(arr.getJSONObject(i))
        prefs.edit().putString(KEY, next.toString()).apply()
    }

    fun all(): List<SaveEvent> {
        val arr = JSONArray(prefs.getString(KEY, "[]") ?: "[]")
        return buildList {
            for (i in 0 until arr.length()) {
                val o = arr.getJSONObject(i)
                add(
                    SaveEvent(
                        video_id = o.optString("video_id"),
                        title = o.optString("title"),
                        channel_title = o.optString("channel_title"),
                        thumb_url = o.optString("thumb_url"),
                        source = o.optString("source"),
                        classify_engine = o.optString("classify_engine"),
                        classify_reason = o.optString("classify_reason"),
                        created_at = o.optString("created_at"),
                        classified_into = o.optJSONArray("classified_into")?.let { a ->
                            (0 until a.length()).map { j ->
                                val c = a.getJSONObject(j)
                                ClassifiedInto(
                                    list_id = if (c.has("list_id") && !c.isNull("list_id")) c.optInt("list_id") else null,
                                    list_title = c.optString("list_title"),
                                )
                            }
                        },
                        in_lists = o.optJSONArray("in_lists")?.let { a ->
                            (0 until a.length()).map { j ->
                                val c = a.getJSONObject(j)
                                ListRef(
                                    id = if (c.has("id") && !c.isNull("id")) c.optInt("id") else null,
                                    title = c.optString("title"),
                                )
                            }
                        },
                        tags = o.optJSONArray("tags")?.let { a ->
                            (0 until a.length()).map { j ->
                                val c = a.getJSONObject(j)
                                TagDto(
                                    id = if (c.has("id") && !c.isNull("id")) c.optInt("id") else null,
                                    name = c.optString("name"),
                                    emoji = c.optString("emoji"),
                                )
                            }
                        },
                    ),
                )
            }
        }
    }

    companion object {
        private const val PREFS = "cq_save_history"
        private const val KEY = "events"
        private const val MAX = 80
    }
}
