"""Light reminders on videos + due scan for digest/push."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from backend import db
from backend import youtube as yt


def _parse_iso(s: str) -> Optional[datetime]:
    raw = (s or "").strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def list_reminders(user_id: int, *, include_done: bool = False) -> list[dict[str, Any]]:
    if include_done:
        rows = db.fetchall(
            """
            SELECT r.id, r.video_id, r.remind_at, r.done,
                   v.title, v.channel_title, v.thumb_url, v.duration_sec
            FROM reminders r
            LEFT JOIN videos v ON v.video_id = r.video_id
            WHERE r.user_id = ?
            ORDER BY r.remind_at ASC
            LIMIT 100
            """,
            (user_id,),
        )
    else:
        rows = db.fetchall(
            """
            SELECT r.id, r.video_id, r.remind_at, r.done,
                   v.title, v.channel_title, v.thumb_url, v.duration_sec
            FROM reminders r
            LEFT JOIN videos v ON v.video_id = r.video_id
            WHERE r.user_id = ? AND COALESCE(r.done, 0) = 0
            ORDER BY r.remind_at ASC
            LIMIT 100
            """,
            (user_id,),
        )
    out = []
    for r in rows:
        out.append(
            {
                "id": int(r["id"]),
                "video_id": r["video_id"],
                "remind_at": str(r.get("remind_at") or ""),
                "done": bool(int(r.get("done") or 0)),
                "title": r.get("title") or r["video_id"],
                "channel_title": r.get("channel_title") or "",
                "thumb_url": r.get("thumb_url") or yt.thumb_url(r["video_id"]),
                "duration_label": yt.format_duration(r.get("duration_sec")),
            }
        )
    return out


def set_reminder(user_id: int, video_id: str, remind_at: str) -> dict[str, Any]:
    video_id = (video_id or "").strip()
    dt = _parse_iso(remind_at)
    if not video_id or not dt:
        return {"ok": False, "error": "Укажите video_id и remind_at (ISO)"}
    lib = db.fetchone(
        "SELECT 1 AS ok FROM library_items WHERE user_id = ? AND video_id = ?",
        (user_id, video_id),
    )
    if not lib:
        return {"ok": False, "error": "Видео нет в библиотеке"}
    iso = dt.astimezone(timezone.utc).isoformat()
    existing = db.fetchone(
        "SELECT id FROM reminders WHERE user_id = ? AND video_id = ? AND COALESCE(done,0)=0",
        (user_id, video_id),
    )
    if existing:
        db.execute(
            "UPDATE reminders SET remind_at = ?, done = 0 WHERE id = ?",
            (iso, int(existing["id"])),
        )
        rid = int(existing["id"])
    else:
        if db.is_postgres():
            row = db.fetchone(
                """
                INSERT INTO reminders (user_id, video_id, remind_at, done)
                VALUES (?, ?, ?, 0) RETURNING id
                """,
                (user_id, video_id, iso),
            )
            rid = int((row or {}).get("id") or 0)
        else:
            db.execute(
                "INSERT INTO reminders (user_id, video_id, remind_at, done) VALUES (?, ?, ?, 0)",
                (user_id, video_id, iso),
            )
            row = db.fetchone("SELECT last_insert_rowid() AS id")
            rid = int((row or {}).get("id") or 0)
    return {"ok": True, "id": rid, "video_id": video_id, "remind_at": iso}


def complete_reminder(user_id: int, reminder_id: int) -> dict[str, Any]:
    db.execute(
        "UPDATE reminders SET done = 1 WHERE id = ? AND user_id = ?",
        (reminder_id, user_id),
    )
    return {"ok": True}


def delete_reminder(user_id: int, reminder_id: int) -> dict[str, Any]:
    db.execute("DELETE FROM reminders WHERE id = ? AND user_id = ?", (reminder_id, user_id))
    return {"ok": True}


def due_reminders(user_id: int) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc).isoformat()
    if db.is_postgres():
        rows = db.fetchall(
            """
            SELECT r.id, r.video_id, r.remind_at, v.title
            FROM reminders r
            LEFT JOIN videos v ON v.video_id = r.video_id
            WHERE r.user_id = ? AND COALESCE(r.done,0)=0 AND r.remind_at <= ?
            ORDER BY r.remind_at ASC LIMIT 20
            """,
            (user_id, now),
        )
    else:
        rows = db.fetchall(
            """
            SELECT r.id, r.video_id, r.remind_at, v.title
            FROM reminders r
            LEFT JOIN videos v ON v.video_id = r.video_id
            WHERE r.user_id = ? AND COALESCE(r.done,0)=0 AND r.remind_at <= ?
            ORDER BY r.remind_at ASC LIMIT 20
            """,
            (user_id, now),
        )
    return [
        {
            "id": int(r["id"]),
            "video_id": r["video_id"],
            "remind_at": str(r.get("remind_at") or ""),
            "title": r.get("title") or r["video_id"],
        }
        for r in rows
    ]
