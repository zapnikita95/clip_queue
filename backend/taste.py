"""Infer viewing habits from Takeout / watched_at and library themes.

YouTube API does not expose watch progress %. Takeout history has timestamps
(when the user watched), which we use for daypart histograms. Confirm UI lets
the user accept or override; silence → we keep the inferred prefs.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from backend import db
from backend import now_plan
from backend import youtube as yt

_DAYPARTS = (
    ("night", 0, 5, "Ночью"),
    ("morning", 5, 12, "Утром"),
    ("day", 12, 18, "Днём"),
    ("evening", 18, 24, "Вечером"),
)

_PROGRESS_HM = re.compile(
    r"^\s*(?:(\d{1,2})\s*[:.]\s*)?(\d{1,2})\s*[:.]\s*(\d{1,2})\s*$"
)
_PROGRESS_MIN = re.compile(
    r"^\s*(\d{1,4})\s*(?:м|мин|min|m)?\s*$",
    re.IGNORECASE,
)
_PROGRESS_PCT = re.compile(r"^\s*(\d{1,3})\s*%\s*$")


def parse_progress_input(raw: str, *, duration_sec: int | None = None) -> int | None:
    """Parse '12:34', '1:02:03', '25 мин', '45%' → seconds. None if empty/invalid."""
    s = (raw or "").strip().replace(",", ".")
    if not s:
        return None
    m = _PROGRESS_PCT.match(s)
    if m:
        pct = max(0, min(100, int(m.group(1))))
        if duration_sec and duration_sec > 0:
            return int(duration_sec * pct / 100)
        return None
    m = _PROGRESS_HM.match(s)
    if m:
        h = int(m.group(1) or 0)
        mm = int(m.group(2))
        ss = int(m.group(3))
        if mm > 59 or ss > 59:
            return None
        return h * 3600 + mm * 60 + ss
    m = _PROGRESS_MIN.match(s)
    if m:
        n = int(m.group(1))
        # bare number: treat as minutes if looks like minutes, else seconds
        if n <= 600 and (duration_sec is None or n * 60 <= (duration_sec + 120)):
            return n * 60
        return n
    return None


def format_progress(sec: int | None) -> str | None:
    if sec is None or sec < 0:
        return None
    h, rem = divmod(int(sec), 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _parse_ts(raw: Any, *, tz: ZoneInfo) -> Optional[datetime]:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        dt = raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
        return dt.astimezone(tz)
    s = str(raw).strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(tz)
    except ValueError:
        return None


def _daypart_for_hour(hour: int) -> str:
    for pid, lo, hi, _ in _DAYPARTS:
        if lo <= hour < hi:
            return pid
    return "evening"


def _user_tz(prefs: dict) -> ZoneInfo:
    name = (prefs.get("timezone") or prefs.get("tz") or "Europe/Moscow").strip()
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("Europe/Moscow")


def infer_taste(user_id: int) -> dict[str, Any]:
    prefs = now_plan.get_prefs(user_id)
    tz = _user_tz(prefs)
    done = bool(prefs.get("taste_onboarding_done"))

    # Timestamps: Takeout watched_at + our mark_watched / open events
    rows = db.fetchall(
        """
        SELECT watched_at AS ts FROM library_items
        WHERE user_id = ? AND watched_at IS NOT NULL
        UNION ALL
        SELECT at AS ts FROM watch_events
        WHERE user_id = ? AND event_type IN (
            'mark_watched', 'mark_started', 'open_yt', 'takeout_history'
        )
        """,
        (user_id, user_id),
    )
    hours: list[int] = []
    for r in rows or []:
        dt = _parse_ts(r.get("ts"), tz=tz)
        if dt:
            hours.append(dt.hour)

    hour_hist = Counter(hours)
    daypart_counts: Counter[str] = Counter()
    for h, n in hour_hist.items():
        daypart_counts[_daypart_for_hour(h)] += n

    dayparts = []
    for pid, _lo, _hi, label in _DAYPARTS:
        dayparts.append(
            {
                "id": pid,
                "label": label,
                "count": int(daypart_counts.get(pid, 0)),
                "share": round(
                    (daypart_counts.get(pid, 0) / max(1, len(hours))) * 100
                ),
            }
        )
    dayparts_sorted = sorted(dayparts, key=lambda x: -int(x["count"]))
    top_dayparts = [d for d in dayparts_sorted if int(d["count"]) > 0][:2]
    if not top_dayparts:
        top_dayparts = [
            {"id": "evening", "label": "Вечером", "count": 0, "share": 0},
            {"id": "morning", "label": "Утром", "count": 0, "share": 0},
        ]

    # Theme / folder taste from lists with most queue+watched items
    list_rows = db.fetchall(
        """
        SELECT l.id, l.title, COUNT(*) AS c
        FROM lists l
        JOIN list_items x ON x.list_id = l.id
        JOIN library_items li
          ON li.video_id = x.video_id AND li.user_id = l.user_id
        WHERE l.user_id = ?
          AND li.status IN ('queue', 'in_progress', 'watched')
          AND COALESCE(l.hidden_from_home, 0) = 0
        GROUP BY l.id, l.title
        ORDER BY c DESC
        LIMIT 8
        """,
        (user_id,),
    )
    themes_out = [
        {
            "id": str(r["id"]),
            "title": (r.get("title") or "").strip() or "Папка",
            "count": int(r.get("c") or 0),
        }
        for r in (list_rows or [])
        if int(r.get("c") or 0) >= 2
    ][:5]

    # Channels: liked + watched
    ch_rows = db.fetchall(
        """
        SELECT v.channel_title, COUNT(*) AS c
        FROM library_items li
        JOIN videos v ON v.video_id = li.video_id
        WHERE li.user_id = ?
          AND (
            li.source = 'liked'
            OR li.status = 'watched'
            OR COALESCE(li.interest, 0) >= 1
          )
          AND COALESCE(v.channel_title, '') <> ''
        GROUP BY v.channel_title
        ORDER BY c DESC
        LIMIT 6
        """,
        (user_id,),
    )
    channels = [
        {"title": r["channel_title"], "count": int(r.get("c") or 0)}
        for r in (ch_rows or [])
    ]

    confirmed = prefs.get("taste_confirm") if isinstance(prefs.get("taste_confirm"), dict) else {}
    sample_n = len(hours)
    enough = sample_n >= 8 or len(themes_out) >= 2

    questions = []
    if top_dayparts:
        a = top_dayparts[0]
        b = top_dayparts[1] if len(top_dayparts) > 1 else {
            "id": "morning" if a["id"] != "morning" else "evening",
            "label": "Утром" if a["id"] != "morning" else "Вечером",
            "count": 0,
            "share": 0,
        }
        questions.append(
            {
                "id": "daypart",
                "prompt": "Когда вы обычно смотрите?",
                "inferred": a["id"],
                "options": [
                    {
                        "id": a["id"],
                        "label": a["label"],
                        "hint": f"по истории · {a['share']}%" if sample_n else "предположение",
                    },
                    {
                        "id": b["id"],
                        "label": b["label"],
                        "hint": f"по истории · {b['share']}%" if sample_n else "альтернатива",
                    },
                    {"id": "any", "label": "В разное время", "hint": "без привязки"},
                ],
            }
        )
    if len(themes_out) >= 2:
        questions.append(
            {
                "id": "theme",
                "prompt": "Что ближе из вашей библиотеки?",
                "inferred": themes_out[0]["id"],
                "options": [
                    {
                        "id": t["id"],
                        "label": t["title"],
                        "hint": f"{t['count']} видео",
                    }
                    for t in themes_out[:3]
                ]
                + [{"id": "skip", "label": "Всё поровну", "hint": ""}],
            }
        )

    return {
        "ok": True,
        "onboarding_done": done,
        "needs_confirm": (not done) and enough and bool(questions),
        "sample_events": sample_n,
        "timezone": str(tz),
        "dayparts": dayparts_sorted,
        "top_dayparts": top_dayparts,
        "themes": themes_out,
        "channels": channels,
        "questions": questions,
        "confirmed": confirmed,
        "copy": {
            "title": "Уточним вкус",
            "subtitle": (
                "Мы посмотрели вашу историю и папки. "
                "Подтвердите — или пропустите, будем опираться на то, что уже видно."
            ),
        },
    }


def confirm_taste(user_id: int, body: dict[str, Any] | None = None) -> dict[str, Any]:
    body = body or {}
    skip = bool(body.get("skip") or body.get("dismiss"))
    answers = body.get("answers") if isinstance(body.get("answers"), dict) else {}
    inferred = infer_taste(user_id)
    patch: dict[str, Any] = {"taste_onboarding_done": True}
    if skip:
        # Lock in inferred defaults so pushes can use them
        top = (inferred.get("top_dayparts") or [{}])[0]
        themes = inferred.get("themes") or []
        patch["taste_confirm"] = {
            "daypart": top.get("id") or "evening",
            "theme_list_id": themes[0]["id"] if themes else None,
            "source": "inferred",
        }
    else:
        daypart = str(answers.get("daypart") or "").strip() or (
            (inferred.get("top_dayparts") or [{}])[0].get("id") or "evening"
        )
        theme = answers.get("theme")
        if theme in (None, "", "skip"):
            theme_id = None
        else:
            theme_id = str(theme)
        patch["taste_confirm"] = {
            "daypart": daypart,
            "theme_list_id": theme_id,
            "source": "user",
        }
        if daypart and daypart != "any":
            # Soft bias for morning/evening digests
            patch["preferred_daypart"] = daypart
    prefs = now_plan.set_prefs(user_id, patch)
    return {"ok": True, "prefs": prefs, "taste": infer_taste(user_id)}


def pending_ratings(user_id: int, *, limit: int = 12) -> list[dict[str, Any]]:
    rows = db.fetchall(
        """
        SELECT v.*, li.status, li.saved_at, li.watched_at, li.interest,
               li.progress_sec, li.rating_pending
        FROM library_items li
        JOIN videos v ON v.video_id = li.video_id
        WHERE li.user_id = ?
          AND COALESCE(li.rating_pending, 0) = 1
          AND li.status = 'watched'
        ORDER BY COALESCE(li.watched_at, li.saved_at) DESC
        LIMIT ?
        """,
        (user_id, limit),
    )
    out = []
    for r in rows or []:
        card = yt.card_from_video_row(
            r,
            {
                "status": r.get("status"),
                "interest": int(r.get("interest") or 0),
                "progress_sec": r.get("progress_sec"),
                "progress_label": format_progress(r.get("progress_sec")),
                "rating_pending": True,
                "watched_at": str(r.get("watched_at") or "") or None,
            },
        )
        out.append(card)
    return out


def mark_rating_pending(user_id: int, video_id: str, pending: bool = True) -> None:
    db.execute(
        "UPDATE library_items SET rating_pending = ? WHERE user_id = ? AND video_id = ?",
        (1 if pending else 0, user_id, video_id),
    )


def set_progress(
    user_id: int,
    video_id: str,
    progress_sec: int | None,
    *,
    status: str | None = "in_progress",
) -> dict[str, Any]:
    sets = ["progress_sec = ?"]
    params: list[Any] = [progress_sec]
    if status in ("queue", "in_progress", "watched", "archived"):
        sets.append("status = ?")
        params.append(status)
        if status == "watched":
            sets.append(
                "watched_at = NOW()"
                if db.is_postgres()
                else "watched_at = datetime('now')"
            )
            sets.append("rating_pending = 1")
            db.execute(
                "INSERT INTO watch_events (user_id, video_id, event_type) VALUES (?, ?, ?)",
                (user_id, video_id, "mark_watched"),
            )
        elif status == "in_progress":
            db.execute(
                "INSERT INTO watch_events (user_id, video_id, event_type) VALUES (?, ?, ?)",
                (user_id, video_id, "mark_progress"),
            )
    params.extend([user_id, video_id])
    db.execute(
        "UPDATE library_items SET "
        + ", ".join(sets)
        + " WHERE user_id = ? AND video_id = ?",
        params,
    )
    return {
        "ok": True,
        "progress_sec": progress_sec,
        "progress_label": format_progress(progress_sec),
        "status": status,
    }
