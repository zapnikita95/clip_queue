"""Sync liked videos + user playlists via YouTube Data API (not WL/history)."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Generator, Optional

import requests

from backend import db, google_oauth
from backend import youtube as yt

YT_API = "https://www.googleapis.com/youtube/v3"
log = logging.getLogger("clip_queue.yt_sync")


def _get(access: str, path: str, params: dict) -> dict:
    log.info("YT GET %s params=%s", path, {k: v for k, v in params.items() if k != "pageToken"})
    r = requests.get(
        f"{YT_API}/{path}",
        params=params,
        headers={"Authorization": f"Bearer {access}"},
        timeout=25,
    )
    if r.status_code != 200:
        log.error("YT GET %s failed %s %s", path, r.status_code, r.text[:400])
        raise RuntimeError(f"YouTube API {path}: {r.status_code} {r.text[:240]}")
    return r.json()


def _upsert_video_from_snippet(video_id: str, sn: dict, duration_sec: Optional[int] = None) -> None:
    thumbs = sn.get("thumbnails") or {}
    thumb = ""
    for k in ("maxres", "standard", "high", "medium", "default"):
        if k in thumbs and thumbs[k].get("url"):
            thumb = thumbs[k]["url"]
            break
    meta = {
        "video_id": video_id,
        "title": (sn.get("title") or "").strip() or f"YouTube {video_id}",
        "description": (sn.get("description") or "").strip()[:4000],
        "channel_id": (sn.get("channelId") or "").strip(),
        "channel_title": (sn.get("channelTitle") or "").strip(),
        "duration_sec": duration_sec,
        "published_at": sn.get("publishedAt"),
        "thumb_url": thumb or yt.thumb_url(video_id),
        "tags": list(sn.get("tags") or [])[:40],
    }
    tags_json = json.dumps(meta["tags"], ensure_ascii=False)
    if db.is_postgres():
        db.execute(
            """
            INSERT INTO videos (
              video_id, title, description, channel_id, channel_title,
              duration_sec, published_at, thumb_url, tags_json, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NOW())
            ON CONFLICT (video_id) DO UPDATE SET
              title = EXCLUDED.title,
              description = EXCLUDED.description,
              channel_id = EXCLUDED.channel_id,
              channel_title = EXCLUDED.channel_title,
              duration_sec = COALESCE(EXCLUDED.duration_sec, videos.duration_sec),
              published_at = COALESCE(EXCLUDED.published_at, videos.published_at),
              thumb_url = EXCLUDED.thumb_url,
              tags_json = EXCLUDED.tags_json,
              fetched_at = NOW()
            """,
            (
                meta["video_id"],
                meta["title"],
                meta["description"],
                meta["channel_id"],
                meta["channel_title"],
                meta["duration_sec"],
                meta["published_at"],
                meta["thumb_url"],
                tags_json,
            ),
        )
    else:
        db.execute(
            """
            INSERT INTO videos (
              video_id, title, description, channel_id, channel_title,
              duration_sec, published_at, thumb_url, tags_json, fetched_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(video_id) DO UPDATE SET
              title = excluded.title,
              description = excluded.description,
              channel_id = excluded.channel_id,
              channel_title = excluded.channel_title,
              duration_sec = COALESCE(excluded.duration_sec, videos.duration_sec),
              published_at = COALESCE(excluded.published_at, videos.published_at),
              thumb_url = excluded.thumb_url,
              tags_json = excluded.tags_json,
              fetched_at = datetime('now')
            """,
            (
                meta["video_id"],
                meta["title"],
                meta["description"],
                meta["channel_id"],
                meta["channel_title"],
                meta["duration_sec"],
                meta["published_at"],
                meta["thumb_url"],
                tags_json,
            ),
        )


def _ensure_library(user_id: int, video_id: str, source: str, status: str = "queue") -> bool:
    """Return True if inserted new."""
    existing = db.fetchone(
        "SELECT video_id FROM library_items WHERE user_id = ? AND video_id = ?",
        (user_id, video_id),
    )
    if existing:
        return False
    db.execute(
        "INSERT INTO library_items (user_id, video_id, status, source) VALUES (?, ?, ?, ?)",
        (user_id, video_id, status, source),
    )
    return True


def _ensure_list(user_id: int, title: str) -> int:
    row = db.fetchone(
        "SELECT id FROM lists WHERE user_id = ? AND title = ?",
        (user_id, title),
    )
    if row:
        return int(row["id"])
    if db.is_postgres():
        with db.connect() as conn:
            cur = conn.execute(
                "INSERT INTO lists (user_id, title) VALUES (%s, %s) RETURNING id",
                (user_id, title),
            )
            return int(cur.fetchone()["id"])
    db.execute("INSERT INTO lists (user_id, title) VALUES (?, ?)", (user_id, title))
    row = db.fetchone(
        "SELECT id FROM lists WHERE user_id = ? AND title = ? ORDER BY id DESC",
        (user_id, title),
    )
    return int(row["id"])


def _add_list_item(list_id: int, video_id: str) -> None:
    db.execute(
        "INSERT INTO list_items (list_id, video_id, position) VALUES (?, ?, 0) "
        + (
            "ON CONFLICT DO NOTHING"
            if db.is_postgres()
            else "ON CONFLICT(list_id, video_id) DO NOTHING"
        ),
        (list_id, video_id),
    )


def _iter_playlist_items(access: str, playlist_id: str, limit: int = 400) -> list[dict]:
    items: list[dict] = []
    page = None
    while len(items) < limit:
        params = {
            "part": "snippet,contentDetails",
            "playlistId": playlist_id,
            "maxResults": min(50, limit - len(items)),
        }
        if page:
            params["pageToken"] = page
        try:
            data = _get(access, "playlistItems", params)
        except RuntimeError as e:
            # WL / HL blocked
            if "403" in str(e) or "404" in str(e):
                break
            raise
        for it in data.get("items") or []:
            sn = it.get("snippet") or {}
            vid = (it.get("contentDetails") or {}).get("videoId") or sn.get("resourceId", {}).get(
                "videoId"
            )
            if not vid:
                continue
            items.append({"video_id": vid, "snippet": sn})
        page = data.get("nextPageToken")
        if not page:
            break
    return items


def _enrich_durations(access: str, video_ids: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i : i + 50]
        if not chunk:
            continue
        data = _get(
            access,
            "videos",
            {"part": "contentDetails,snippet", "id": ",".join(chunk)},
        )
        for item in data.get("items") or []:
            vid = item.get("id")
            dur = yt._iso8601_duration_to_sec(
                ((item.get("contentDetails") or {}).get("duration") or "")
            )
            if vid and dur is not None:
                out[vid] = dur
            sn = item.get("snippet") or {}
            if vid and sn:
                _upsert_video_from_snippet(vid, sn, duration_sec=dur)
    return out


def iter_sync_youtube_library(user_id: int) -> Generator[dict[str, Any], None, None]:
    """Yield NDJSON-friendly progress events, then a final {type: done, stats}."""
    t0 = time.time()

    def emit(pct: int, title: str, detail: str = "") -> dict[str, Any]:
        elapsed = time.time() - t0
        eta = None
        if 4 <= pct < 100:
            eta = max(1, round(elapsed / pct * (100 - pct)))
        return {
            "type": "progress",
            "pct": max(0, min(99, int(pct))),
            "title": title,
            "detail": detail,
            "elapsed_sec": int(elapsed),
            "eta_sec": eta,
        }

    stats: dict[str, Any] = {
        "liked_new": 0,
        "liked_total": 0,
        "playlists": 0,
        "playlist_items_new": 0,
        "subscriptions": 0,
        "skipped_private": [],
        "notes": [
            "Watch Later и история просмотров через YouTube API недоступны (ограничение Google).",
            "Загрузи Takeout, если нужна история.",
        ],
    }

    yield emit(3, "Подключаюсь к YouTube", "Проверяю Google-доступ и обновляю токен")
    access = google_oauth.get_valid_access_token(user_id)

    yield emit(8, "Читаю твой канал", "Ищу плейлист лайков")
    ch = _get(
        access,
        "channels",
        {"part": "contentDetails,snippet", "mine": "true"},
    )
    ch_items = ch.get("items") or []
    likes_pl = None
    if ch_items:
        related = (ch_items[0].get("contentDetails") or {}).get("relatedPlaylists") or {}
        likes_pl = related.get("likes")

    if likes_pl:
        yield emit(14, "Тяну лайки", "Загружаю список понравившихся видео")
        liked = _iter_playlist_items(access, likes_pl, limit=500)
        stats["liked_total"] = len(liked)
        ids = [x["video_id"] for x in liked]
        yield emit(
            22,
            "Сохраняю лайки",
            f"Найдено {len(liked)} · подтягиваю длительности и превью",
        )
        _enrich_durations(access, ids)
        list_id = _ensure_list(user_id, "Лайки YouTube")
        for i, x in enumerate(liked):
            vid = x["video_id"]
            if not db.fetchone("SELECT video_id FROM videos WHERE video_id = ?", (vid,)):
                _upsert_video_from_snippet(vid, x.get("snippet") or {})
            if _ensure_library(user_id, vid, source="liked", status="queue"):
                stats["liked_new"] += 1
            _add_list_item(list_id, vid)
            if liked and i % 40 == 0:
                pct = 22 + int(10 * (i + 1) / max(1, len(liked)))
                yield emit(pct, "Сохраняю лайки", f"{i + 1} из {len(liked)}")
    else:
        yield emit(20, "Лайки недоступны", "У канала нет открытого плейлиста лайков — иду дальше")

    yield emit(36, "Читаю плейлисты", "Список твоих плейлистов на YouTube")
    page = None
    playlists: list[dict] = []
    while len(playlists) < 40:
        params = {"part": "snippet,contentDetails", "mine": "true", "maxResults": 50}
        if page:
            params["pageToken"] = page
        data = _get(access, "playlists", params)
        playlists.extend(data.get("items") or [])
        page = data.get("nextPageToken")
        if not page:
            break

    work_pls = []
    for pl in playlists:
        pl_id = pl.get("id")
        title = ((pl.get("snippet") or {}).get("title") or "Плейлист").strip()
        if pl_id in ("WL", "HL") or title.lower() in ("watch later", "смотреть позже"):
            stats["skipped_private"].append(title or pl_id)
            continue
        work_pls.append((pl_id, title))

    n_pl = max(1, len(work_pls))
    for pi, (pl_id, title) in enumerate(work_pls):
        base = 40 + int(40 * pi / n_pl)
        yield emit(
            base,
            f"Плейлист: {title[:48]}",
            f"{pi + 1} из {len(work_pls)} · качаю ролики",
        )
        stats["playlists"] += 1
        items = _iter_playlist_items(access, pl_id, limit=300)
        ids = [x["video_id"] for x in items]
        _enrich_durations(access, ids)
        list_id = _ensure_list(user_id, f"YT: {title}"[:120])
        for x in items:
            vid = x["video_id"]
            if not db.fetchone("SELECT video_id FROM videos WHERE video_id = ?", (vid,)):
                _upsert_video_from_snippet(vid, x.get("snippet") or {})
            if _ensure_library(user_id, vid, source="playlist", status="queue"):
                stats["playlist_items_new"] += 1
            _add_list_item(list_id, vid)
        yield emit(
            40 + int(40 * (pi + 1) / n_pl),
            f"Плейлист: {title[:48]}",
            f"Готово · {len(items)} видео",
        )

    yield emit(84, "Тяну подписки", "Каналы для подсказок по структуре")
    page = None
    subs = 0
    while subs < 200:
        params = {"part": "snippet", "mine": "true", "maxResults": 50}
        if page:
            params["pageToken"] = page
        data = _get(access, "subscriptions", params)
        for it in data.get("items") or []:
            sn = it.get("snippet") or {}
            ch_title = (sn.get("title") or "").strip()
            ch_id = ((sn.get("resourceId") or {}).get("channelId") or "").strip()
            if ch_id:
                db.execute(
                    "INSERT INTO subscriptions (user_id, channel_id, channel_title) VALUES (?, ?, ?) "
                    + (
                        "ON CONFLICT (user_id, channel_id) DO UPDATE SET channel_title = EXCLUDED.channel_title"
                        if db.is_postgres()
                        else "ON CONFLICT(user_id, channel_id) DO UPDATE SET channel_title = excluded.channel_title"
                    ),
                    (user_id, ch_id, ch_title),
                )
                subs += 1
        page = data.get("nextPageToken")
        if not page:
            break
        yield emit(88, "Тяну подписки", f"Уже {subs} каналов")
    stats["subscriptions"] = subs

    yield emit(95, "Записываю итог", "Сохраняю отчёт синка")
    db.execute(
        "INSERT INTO sync_runs (user_id, kind, status, stats_json) VALUES (?, ?, ?, ?)",
        (user_id, "youtube_oauth", "ok", json.dumps(stats, ensure_ascii=False)),
    )
    elapsed = int(time.time() - t0)
    yield {
        "type": "done",
        "pct": 100,
        "title": "Синк готов",
        "detail": f"Лайки: +{stats['liked_new']} · плейлисты: {stats['playlists']} · подписки: {stats['subscriptions']}",
        "elapsed_sec": elapsed,
        "eta_sec": 0,
        "stats": stats,
    }


def sync_youtube_library(user_id: int) -> dict[str, Any]:
    stats: dict[str, Any] = {}
    for ev in iter_sync_youtube_library(user_id):
        if ev.get("type") == "done":
            stats = ev.get("stats") or {}
    return stats
