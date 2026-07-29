"""Sync liked videos + user playlists via YouTube Data API (not WL/history)."""

from __future__ import annotations

import json
import logging
import os
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
    """Return True if inserted new. Never resurrects dismissed (rejected) videos."""
    existing = db.fetchone(
        "SELECT video_id, status FROM library_items WHERE user_id = ? AND video_id = ?",
        (user_id, video_id),
    )
    if existing:
        # Keep rejected/hidden out of queue forever — sync must not bring them back
        return False
    db.execute(
        "INSERT INTO library_items (user_id, video_id, status, source) VALUES (?, ?, ?, ?)",
        (user_id, video_id, status, source),
    )
    return True


def _touch_library_saved_at(user_id: int, video_id: str, when: str | None = None) -> None:
    """Bump saved_at so «Недавно добавлены» picks up inbox / playlist adds."""
    if db.is_postgres():
        if when:
            db.execute(
                "UPDATE library_items SET saved_at = GREATEST(saved_at, %s::timestamptz) "
                "WHERE user_id = %s AND video_id = %s AND status IN ('queue', 'in_progress')",
                (when, user_id, video_id),
            )
        else:
            db.execute(
                "UPDATE library_items SET saved_at = NOW() "
                "WHERE user_id = %s AND video_id = %s AND status IN ('queue', 'in_progress')",
                (user_id, video_id),
            )
    else:
        if when:
            db.execute(
                "UPDATE library_items SET saved_at = ? "
                "WHERE user_id = ? AND video_id = ? AND status IN ('queue', 'in_progress') "
                "AND (saved_at IS NULL OR datetime(saved_at) < datetime(?))",
                (when, user_id, video_id, when),
            )
        else:
            db.execute(
                "UPDATE library_items SET saved_at = datetime('now') "
                "WHERE user_id = ? AND video_id = ? AND status IN ('queue', 'in_progress')",
                (user_id, video_id),
            )


def is_inbox_playlist_title(title: str) -> bool:
    """User's «спецпапка» for stuff to watch: Listen later / смотреть позже / etc."""
    t = (title or "").strip().lower()
    if t.startswith("yt:"):
        t = t[3:].strip()
    if not t:
        return False
    if t in (
        "listen later",
        "слушать позже",
        "смотреть позже",
        "сомтреть позже",
        "watch later",
    ):
        return True
    if "listen later" in t:
        return True
    if "позже" in t and any(
        x in t for x in ("смотр", "сомтр", "listen", "тест", "очеред", "inbox", "to watch")
    ):
        return True
    return False


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


def _add_list_item(
    list_id: int,
    video_id: str,
    position: int = 0,
    *,
    added_at: str | None = None,
    refresh: bool = False,
) -> bool:
    """Insert list membership. Returns True if the row was newly inserted."""
    before = db.fetchone(
        "SELECT 1 AS x FROM list_items WHERE list_id = ? AND video_id = ?",
        (list_id, video_id),
    )
    if refresh:
        if added_at:
            if db.is_postgres():
                db.execute(
                    """
                    INSERT INTO list_items (list_id, video_id, position, added_at)
                    VALUES (?, ?, ?, ?::timestamptz)
                    ON CONFLICT (list_id, video_id) DO UPDATE SET
                      position = EXCLUDED.position,
                      added_at = EXCLUDED.added_at
                    """,
                    (list_id, video_id, position, added_at),
                )
            else:
                db.execute(
                    """
                    INSERT INTO list_items (list_id, video_id, position, added_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(list_id, video_id) DO UPDATE SET
                      position = excluded.position,
                      added_at = excluded.added_at
                    """,
                    (list_id, video_id, position, added_at),
                )
        else:
            db.execute(
                """
                INSERT INTO list_items (list_id, video_id, position) VALUES (?, ?, ?)
                ON CONFLICT(list_id, video_id) DO UPDATE SET position = excluded.position
                """
                if not db.is_postgres()
                else """
                INSERT INTO list_items (list_id, video_id, position) VALUES (?, ?, ?)
                ON CONFLICT (list_id, video_id) DO UPDATE SET position = EXCLUDED.position
                """,
                (list_id, video_id, position),
            )
        return before is None

    if added_at:
        if db.is_postgres():
            db.execute(
                """
                INSERT INTO list_items (list_id, video_id, position, added_at)
                VALUES (?, ?, ?, ?::timestamptz)
                ON CONFLICT DO NOTHING
                """,
                (list_id, video_id, position, added_at),
            )
        else:
            db.execute(
                """
                INSERT INTO list_items (list_id, video_id, position, added_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(list_id, video_id) DO NOTHING
                """,
                (list_id, video_id, position, added_at),
            )
    else:
        db.execute(
            "INSERT INTO list_items (list_id, video_id, position) VALUES (?, ?, ?) "
            + (
                "ON CONFLICT DO NOTHING"
                if db.is_postgres()
                else "ON CONFLICT(list_id, video_id) DO NOTHING"
            ),
            (list_id, video_id, position),
        )
    return before is None


def _list_video_ids(list_id: int) -> set[str]:
    return {
        r["video_id"]
        for r in db.fetchall(
            "SELECT video_id FROM list_items WHERE list_id = ?", (list_id,)
        )
    }


def _iter_playlist_items(
    access: str,
    playlist_id: str,
    limit: int = 400,
    *,
    known_ids: set[str] | None = None,
    stop_after_known: int = 0,
    include_known: bool = False,
) -> list[dict]:
    """Page playlist items.

    stop_after_known: stop after N consecutive ids already in known_ids
    (likes newest-first → cheap delta).
    include_known=True: still yield known ids (for refreshing added_at on inbox).
    """
    items: list[dict] = []
    page = None
    consecutive_known = 0
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
        batch = data.get("items") or []
        if not batch:
            break
        for it in batch:
            sn = it.get("snippet") or {}
            vid = (it.get("contentDetails") or {}).get("videoId") or sn.get("resourceId", {}).get(
                "videoId"
            )
            if not vid:
                continue
            is_known = known_ids is not None and vid in known_ids
            if is_known and stop_after_known > 0:
                consecutive_known += 1
                if consecutive_known >= stop_after_known:
                    if include_known:
                        items.append({"video_id": vid, "snippet": sn, "already_in": True})
                    return items
                if include_known:
                    items.append({"video_id": vid, "snippet": sn, "already_in": True})
                    if len(items) >= limit:
                        break
                continue
            consecutive_known = 0
            items.append({"video_id": vid, "snippet": sn, "already_in": bool(is_known)})
            if len(items) >= limit:
                break
        page = data.get("nextPageToken")
        if not page:
            break
    return items


def _library_video_ids(user_id: int) -> set[str]:
    rows = db.fetchall(
        "SELECT video_id FROM library_items WHERE user_id = ?",
        (user_id,),
    )
    return {str(r["video_id"]) for r in rows}


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


def iter_sync_youtube_library(
    user_id: int,
    *,
    full: bool = False,
) -> Generator[dict[str, Any], None, None]:
    """Yield NDJSON-friendly progress events, then a final {type: done, stats}.

    full=False (default): delta — stop paging a source after consecutive already-known items.
    full=True: deep crawl (first onboard / manual «полный синк»).
    """
    t0 = time.time()
    known = _library_video_ids(user_id)
    # First-time library → always full
    if not known:
        full = True
    mode = "полный" if full else "дельта (только новое)"

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
        "liked_scanned": 0,
        "playlists": 0,
        "playlist_items_new": 0,
        "subscriptions": 0,
        "mode": "full" if full else "delta",
        "skipped_private": [],
        "notes": [
            "Watch Later и история через YouTube API недоступны.",
            f"Режим синка: {mode}.",
        ],
    }

    yield emit(3, "Подключаюсь к YouTube", f"Режим: {mode}")
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
        yield emit(14, "Тяну лайки", "Только новые сверху" if not full else "Глубокий обход")
        likes_limit = int(os.environ.get("YT_LIKES_SYNC_LIMIT", "5000") or 5000)
        likes_limit = max(500, min(likes_limit, 15000))
        if not full:
            likes_limit = min(likes_limit, 800)
        stop_known = 0 if full else 35
        liked = _iter_playlist_items(
            access,
            likes_pl,
            limit=likes_limit,
            known_ids=known,
            stop_after_known=stop_known,
        )
        stats["liked_scanned"] = len(liked)
        stats["liked_total"] = len(liked)
        ids = [x["video_id"] for x in liked]
        yield emit(
            22,
            "Сохраняю лайки",
            f"Новых кандидатов: {len(liked)}" + ("" if full else " · дальше уже известные"),
        )
        if ids:
            _enrich_durations(access, ids)
        list_id = _ensure_list(user_id, "Лайки YouTube")
        for i, x in enumerate(liked):
            vid = x["video_id"]
            if not db.fetchone("SELECT video_id FROM videos WHERE video_id = ?", (vid,)):
                _upsert_video_from_snippet(vid, x.get("snippet") or {})
            if _ensure_library(user_id, vid, source="liked", status="queue"):
                stats["liked_new"] += 1
                known.add(vid)
                try:
                    from backend import organize as _org

                    _org.classify_new_video(user_id, vid, use_llm=False)
                except Exception as e:
                    log.warning("auto-classify liked %s: %s", vid, e)
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
    inbox_pls = []
    for pl in playlists:
        pl_id = pl.get("id")
        title = ((pl.get("snippet") or {}).get("title") or "Плейлист").strip()
        if pl_id in ("WL", "HL") or title.lower() in ("watch later", "смотреть позже"):
            # System WL is blocked by Google; user-made «смотреть позже» / Listen later — ok
            if pl_id in ("WL", "HL"):
                stats["skipped_private"].append(title or pl_id)
                continue
            # title literally "смотреть позже" as custom playlist — treat as inbox below
        entry = (pl_id, title)
        if is_inbox_playlist_title(title):
            inbox_pls.append(entry)
        else:
            work_pls.append(entry)
    # Спецпапки (Listen later / «смотреть позже») — всегда первыми
    work_pls = inbox_pls + work_pls
    stats["inbox_playlists"] = [t for _, t in inbox_pls]

    n_pl = max(1, len(work_pls))
    for pi, (pl_id, title) in enumerate(work_pls):
        base = 40 + int(40 * pi / n_pl)
        is_inbox = is_inbox_playlist_title(title)
        yield emit(
            base,
            f"{'Спецпапка' if is_inbox else 'Плейлист'}: {title[:48]}",
            f"{pi + 1} из {len(work_pls)} · " + ("полный" if full else "дельта"),
        )
        stats["playlists"] += 1
        list_id = _ensure_list(user_id, f"YT: {title}"[:120])
        in_list = _list_video_ids(list_id)

        pl_limit = int(os.environ.get("YT_PLAYLIST_SYNC_LIMIT", "2000") or 2000)
        pl_limit = max(300, min(pl_limit, 5000))
        if not full:
            pl_limit = min(pl_limit, 400 if is_inbox else 250)
        # Delta: stop after consecutive already-in-THIS-list (not whole library!)
        stop_known = 0 if full else (25 if is_inbox else 20)
        # Inbox: refresh added_at from YouTube for head of list so «Недавно» is real
        include_known = bool(is_inbox and (full or True))
        if is_inbox and not full:
            # Always refresh top of inbox (even known) so dates/order stay true
            stop_known = 40
            include_known = True
            pl_limit = min(max(pl_limit, 80), 150)
            # Demote old positions so YouTube head (0..n) wins in «Недавно»
            db.execute(
                "UPDATE list_items SET position = position + 100000 "
                "WHERE list_id = ? AND position < 100000",
                (list_id,),
            )

        items = _iter_playlist_items(
            access,
            pl_id,
            limit=pl_limit,
            known_ids=in_list,
            stop_after_known=stop_known,
            include_known=include_known if is_inbox else False,
        )
        ids = [x["video_id"] for x in items]
        if ids:
            _enrich_durations(access, ids)
        new_in_pl = 0
        for pos, x in enumerate(items):
            vid = x["video_id"]
            sn = x.get("snippet") or {}
            added_at = (sn.get("publishedAt") or "").strip() or None
            if not db.fetchone("SELECT video_id FROM videos WHERE video_id = ?", (vid,)):
                _upsert_video_from_snippet(vid, sn)
            inserted_lib = _ensure_library(user_id, vid, source="playlist", status="queue")
            if inserted_lib:
                stats["playlist_items_new"] += 1
                known.add(vid)
                try:
                    from backend import organize as _org

                    _org.classify_new_video(user_id, vid, use_llm=False)
                except Exception as e:
                    log.warning("auto-classify playlist %s: %s", vid, e)
            was_new_membership = _add_list_item(
                list_id,
                vid,
                position=pos,
                added_at=added_at,
                refresh=bool(is_inbox),
            )
            if was_new_membership or inserted_lib:
                new_in_pl += 1
                if is_inbox:
                    _touch_library_saved_at(user_id, vid, added_at)
            elif is_inbox and added_at:
                # Keep library «recent» aligned with when user put it in the inbox folder
                _touch_library_saved_at(user_id, vid, added_at)
        if is_inbox:
            stats["inbox_new"] = int(stats.get("inbox_new") or 0) + new_in_pl
        yield emit(
            40 + int(40 * (pi + 1) / n_pl),
            f"{'Спецпапка' if is_inbox else 'Плейлист'}: {title[:48]}",
            f"В пачке: {len(items)} · новых в папке: {new_in_pl}",
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
            thumbs = sn.get("thumbnails") or {}
            thumb = (
                ((thumbs.get("medium") or {}).get("url"))
                or ((thumbs.get("default") or {}).get("url"))
                or ((thumbs.get("high") or {}).get("url"))
                or ""
            )
            if ch_id:
                db.execute(
                    "INSERT INTO subscriptions (user_id, channel_id, channel_title, thumb_url) "
                    "VALUES (?, ?, ?, ?) "
                    + (
                        "ON CONFLICT (user_id, channel_id) DO UPDATE SET "
                        "channel_title = EXCLUDED.channel_title, "
                        "thumb_url = CASE WHEN EXCLUDED.thumb_url != '' THEN EXCLUDED.thumb_url "
                        "ELSE subscriptions.thumb_url END"
                        if db.is_postgres()
                        else "ON CONFLICT(user_id, channel_id) DO UPDATE SET "
                        "channel_title = excluded.channel_title, "
                        "thumb_url = CASE WHEN excluded.thumb_url != '' THEN excluded.thumb_url "
                        "ELSE subscriptions.thumb_url END"
                    ),
                    (user_id, ch_id, ch_title, thumb),
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


def sync_youtube_library(user_id: int, *, full: bool = False) -> dict[str, Any]:
    stats: dict[str, Any] = {}
    for ev in iter_sync_youtube_library(user_id, full=full):
        if ev.get("type") == "done":
            stats = ev.get("stats") or {}
    return stats
