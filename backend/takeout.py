"""Import Google Takeout YouTube watch-history.json."""

from __future__ import annotations

import json
import re
from typing import Any

from backend import db
from backend import youtube as yt

VID_RE = re.compile(
    r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([A-Za-z0-9_-]{6,20})"
)


def _extract_video_id(url: str) -> str | None:
    if not url:
        return None
    m = VID_RE.search(url)
    return m.group(1) if m else yt.extract_video_id(url)


def import_watch_history(user_id: int, payload: Any, limit: int = 2000) -> dict:
    """
    Accepts either a list of Takeout history objects or {"history": [...]} wrapper.
    Each item typically has title, titleUrl, time.
    """
    if isinstance(payload, dict):
        items = payload.get("history") or payload.get("Watch History") or payload.get("items")
        if items is None and "titleUrl" in payload:
            items = [payload]
        if items is None:
            # sometimes the file IS the list nested oddly
            items = []
            for v in payload.values():
                if isinstance(v, list):
                    items = v
                    break
    elif isinstance(payload, list):
        items = payload
    else:
        raise ValueError("Ожидался JSON массив или объект Takeout")

    stats = {"parsed": 0, "imported_new": 0, "skipped": 0, "resolved": 0}
    seen: set[str] = set()

    for raw in items:
        if stats["parsed"] >= limit:
            break
        if not isinstance(raw, dict):
            continue
        url = raw.get("titleUrl") or raw.get("url") or ""
        title = (raw.get("title") or "").strip()
        if title.lower().startswith("watched "):
            title = title[8:].strip()
        vid = _extract_video_id(url)
        if not vid or vid in seen:
            stats["skipped"] += 1
            continue
        seen.add(vid)
        stats["parsed"] += 1

        # lightweight upsert without live resolve (quota)
        existing = db.fetchone("SELECT video_id FROM videos WHERE video_id = ?", (vid,))
        if not existing:
            db.execute(
                "INSERT INTO videos (video_id, title, thumb_url) VALUES (?, ?, ?)",
                (vid, title or f"YouTube {vid}", yt.thumb_url(vid)),
            )
        else:
            if title:
                db.execute(
                    "UPDATE videos SET title = CASE WHEN title = '' OR title LIKE 'YouTube %' "
                    "THEN ? ELSE title END WHERE video_id = ?",
                    (title, vid),
                )

        row = db.fetchone(
            "SELECT * FROM library_items WHERE user_id = ? AND video_id = ?",
            (user_id, vid),
        )
        watched_at = raw.get("time") or raw.get("timestamp")
        if not row:
            db.execute(
                "INSERT INTO library_items (user_id, video_id, status, source, watched_at) "
                "VALUES (?, ?, 'watched', 'takeout', ?)",
                (user_id, vid, watched_at),
            )
            stats["imported_new"] += 1
        else:
            # history implies already seen — promote queue → watched
            if row.get("status") == "queue":
                db.execute(
                    "UPDATE library_items SET status = 'watched', source = CASE "
                    "WHEN source IN ('liked','playlist') THEN source ELSE 'takeout' END, "
                    "watched_at = COALESCE(watched_at, ?) "
                    "WHERE user_id = ? AND video_id = ?",
                    (watched_at, user_id, vid),
                )

        db.execute(
            "INSERT INTO watch_events (user_id, video_id, event_type) VALUES (?, ?, ?)",
            (user_id, vid, "takeout_history"),
        )

    list_id = None
    if stats["parsed"]:
        # ensure list
        existing_list = db.fetchone(
            "SELECT id FROM lists WHERE user_id = ? AND title = ?",
            (user_id, "История Takeout"),
        )
        if existing_list:
            list_id = int(existing_list["id"])
        else:
            if db.is_postgres():
                with db.connect() as conn:
                    cur = conn.execute(
                        "INSERT INTO lists (user_id, title) VALUES (%s, %s) RETURNING id",
                        (user_id, "История Takeout"),
                    )
                    list_id = int(cur.fetchone()["id"])
            else:
                db.execute(
                    "INSERT INTO lists (user_id, title) VALUES (?, ?)",
                    (user_id, "История Takeout"),
                )
                list_id = int(
                    db.fetchone(
                        "SELECT id FROM lists WHERE user_id = ? AND title = ?",
                        (user_id, "История Takeout"),
                    )["id"]
                )
        for vid in list(seen)[:limit]:
            db.execute(
                "INSERT INTO list_items (list_id, video_id, position) VALUES (?, ?, 0) "
                + (
                    "ON CONFLICT DO NOTHING"
                    if db.is_postgres()
                    else "ON CONFLICT(list_id, video_id) DO NOTHING"
                ),
                (list_id, vid),
            )

    db.execute(
        "INSERT INTO sync_runs (user_id, kind, status, stats_json) VALUES (?, ?, ?, ?)",
        (user_id, "takeout_history", "ok", json.dumps(stats, ensure_ascii=False)),
    )
    stats["list_id"] = list_id
    stats["notes"] = [
        "Takeout даёт историю просмотров, но не процент «не досмотрел».",
        "Для Watch Later Google API закрыт — нужен Takeout/расширение/ручное добавление.",
    ]
    return stats
