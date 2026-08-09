"""«Сейчас» — что смотреть из своей библиотеки под слот времени и сценарий."""

from __future__ import annotations

from typing import Any, Optional

from backend import db
from backend import youtube as yt

# Duration slots (seconds)
SLOTS = {
    "short": (0, 15 * 60, "До 15 минут"),
    "medium": (15 * 60, 40 * 60, "15–40 минут"),
    "long": (40 * 60, 10 * 3600, "40+ минут"),
    "any": (0, 10 * 3600, "Любая длина"),
}

MOODS = {
    "learn": {
        "label": "Учиться",
        "hint": "разбор, урок, обучение",
        "keywords": (
            "урок", "обучение", "разбор", "как", "tutorial", "course", "объясн",
            "лекция", "english", "язык", "пдд", "вожд",
        ),
    },
    "deep": {
        "label": "Глубокий разбор",
        "hint": "длинный серьёзный контент",
        "keywords": (
            "разбор", "почему", "история", "анализ", "документал", "исследование",
            "фильм", "теория",
        ),
    },
    "background": {
        "label": "На фоне",
        "hint": "можно слушать вполглаза",
        "keywords": (
            "подкаст", "стрим", "реакция", "podcast", "лонгрид", "беседы",
        ),
    },
    "fun": {
        "label": "Легко",
        "hint": "юмор и отдых",
        "keywords": (
            "юмор", "смешн", "comedy", "прикол", "стендап", "мем",
        ),
    },
}


def _card(row: dict, *, reason: str = "") -> dict[str, Any]:
    vid = row["video_id"]
    return {
        "video_id": vid,
        "title": row.get("title") or vid,
        "channel_title": row.get("channel_title") or "",
        "duration_sec": row.get("duration_sec"),
        "duration_label": yt.format_duration(row.get("duration_sec")),
        "thumb_url": row.get("thumb_url") or yt.thumb_url(vid),
        "watch_url": f"https://www.youtube.com/watch?v={vid}",
        "status": row.get("status") or "queue",
        "interest": int(row.get("interest") or 0),
        "note": row.get("note") or "",
        "reason": reason,
    }


def _eligible(row: dict) -> bool:
    if yt.is_unavailable_video(row.get("title")):
        return False
    bucket = yt.content_bucket(
        row.get("title"), row.get("channel_title"), row.get("duration_sec"), None
    )
    return bucket not in ("music", "shorts", "shortform", "unavailable", "marathon")


def _slot_ok(dur: Optional[int], slot: str) -> bool:
    if slot not in SLOTS:
        slot = "any"
    lo, hi, _ = SLOTS[slot]
    if dur is None:
        return slot == "any"
    try:
        d = int(dur)
    except (TypeError, ValueError):
        return slot == "any"
    return lo <= d < hi


def _mood_score(row: dict, mood: str) -> float:
    if not mood or mood not in MOODS:
        return 0.0
    blob = f"{row.get('title') or ''} {row.get('note') or ''} {row.get('channel_title') or ''}".lower()
    hits = sum(1 for k in MOODS[mood]["keywords"] if k in blob)
    return float(hits)


def fetch_plan_pool(user_id: int, *, limit: int = 400) -> list[dict]:
    rows = db.fetchall(
        """
        SELECT v.video_id, v.title, v.channel_title, v.duration_sec, v.thumb_url,
               li.status, li.interest, li.note, li.saved_at
        FROM library_items li
        JOIN videos v ON v.video_id = li.video_id
        WHERE li.user_id = ?
          AND li.status IN ('queue', 'in_progress')
        ORDER BY
          CASE WHEN li.status = 'in_progress' THEN 0 ELSE 1 END,
          COALESCE(li.interest, 0) DESC,
          li.saved_at DESC
        LIMIT ?
        """,
        (user_id, limit),
    )
    return [r for r in rows if _eligible(r)]


def pick_now(
    user_id: int,
    *,
    slot: str = "any",
    mood: str = "",
    limit: int = 6,
) -> dict[str, Any]:
    """Return picks for «Сейчас» + started + suggestions."""
    pool = fetch_plan_pool(user_id)
    started = [_card(r, reason="Начали смотреть") for r in pool if r.get("status") == "in_progress"][:4]

    candidates = []
    for r in pool:
        if not _slot_ok(r.get("duration_sec"), slot):
            continue
        sc = float(r.get("interest") or 0) * 3.0
        if r.get("status") == "in_progress":
            sc += 5.0
        ms = _mood_score(r, mood)
        if mood and ms <= 0 and mood in MOODS:
            continue
        sc += ms * 2.0
        if (r.get("note") or "").strip():
            sc += 0.5
        candidates.append((sc, r, ms))
    candidates.sort(key=lambda x: -x[0])

    picks = []
    seen = set()
    for sc, r, ms in candidates:
        vid = r["video_id"]
        if vid in seen:
            continue
        seen.add(vid)
        reason = "Под ваш слот времени"
        if r.get("status") == "in_progress":
            reason = "Продолжить"
        elif int(r.get("interest") or 0) >= 2:
            reason = "Отметили как очень интересное"
        elif mood and ms > 0:
            reason = f"Под сценарий «{MOODS[mood]['label']}»"
        elif (r.get("note") or "").strip():
            reason = "Есть ваша заметка"
        picks.append(_card(r, reason=reason))
        if len(picks) >= limit:
            break

    suggestions = _suggestions(user_id, pool, exclude=seen, limit=4)
    return {
        "slot": slot,
        "slot_label": SLOTS.get(slot, SLOTS["any"])[2],
        "mood": mood or None,
        "mood_label": (MOODS.get(mood) or {}).get("label"),
        "picks": picks,
        "started": started,
        "suggestions": suggestions,
        "moods": [{"id": k, "label": v["label"], "hint": v["hint"]} for k, v in MOODS.items()],
        "slots": [{"id": k, "label": v[2]} for k, v in SLOTS.items()],
    }


def _suggestions(
    user_id: int,
    pool: list[dict],
    *,
    exclude: set[str],
    limit: int = 4,
) -> list[dict]:
    """Heuristic nudges: stale high-interest, empty notes folder themes, short wins."""
    out: list[dict] = []
    # High interest not started
    for r in pool:
        if r["video_id"] in exclude:
            continue
        if int(r.get("interest") or 0) >= 1 and r.get("status") == "queue":
            out.append(_card(r, reason="Вы хотели это посмотреть"))
            exclude.add(r["video_id"])
            break
    # Short win
    for r in pool:
        if r["video_id"] in exclude:
            continue
        dur = r.get("duration_sec")
        if isinstance(dur, int) and 3 * 60 <= dur <= 12 * 60:
            out.append(_card(r, reason="Короткий слот — можно сейчас"))
            exclude.add(r["video_id"])
            break
    # With personal note
    for r in pool:
        if r["video_id"] in exclude:
            continue
        if (r.get("note") or "").strip():
            out.append(_card(r, reason="По вашей формулировке"))
            exclude.add(r["video_id"])
            break
    # Fallback: next in interest order
    for r in pool:
        if len(out) >= limit:
            break
        if r["video_id"] in exclude:
            continue
        out.append(_card(r, reason="Из вашей очереди"))
        exclude.add(r["video_id"])
    return out[:limit]


def weekly_digest(user_id: int) -> dict[str, Any]:
    """Build a weekly digest payload (push/copy); does not send by itself."""
    pool = fetch_plan_pool(user_id, limit=200)
    queue_n = sum(1 for r in pool if r.get("status") == "queue")
    started_n = sum(1 for r in pool if r.get("status") == "in_progress")
    now = pick_now(user_id, slot="any", limit=3)
    weekend = pick_now(user_id, slot="long", limit=2)
    lines = [
        f"В очереди {queue_n} роликов"
        + (f", начатых — {started_n}" if started_n else ""),
    ]
    if now["picks"]:
        lines.append("Идеи на эту неделю:")
        for p in now["picks"][:3]:
            lines.append(f"· {p['title'][:70]}")
    if weekend["picks"]:
        lines.append("На выходные (длиннее):")
        for p in weekend["picks"][:2]:
            lines.append(f"· {p['title'][:70]}")
    title = "Kyro: что можно посмотреть"
    body = f"{queue_n} в очереди · {len(now['picks'])} идей на неделю"
    return {
        "title": title,
        "body": body,
        "text": "\n".join(lines),
        "picks": now["picks"],
        "weekend": weekend["picks"],
        "queue_count": queue_n,
        "started_count": started_n,
    }


def ensure_prefs_table() -> None:
    if db.is_postgres():
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS user_prefs (
              user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
              prefs_json TEXT NOT NULL DEFAULT '{}',
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
    else:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS user_prefs (
              user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
              prefs_json TEXT NOT NULL DEFAULT '{}',
              updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )


def get_prefs(user_id: int) -> dict[str, Any]:
    import json

    ensure_prefs_table()
    row = db.fetchone("SELECT prefs_json FROM user_prefs WHERE user_id = ?", (user_id,))
    if not row:
        return {"digest_enabled": True, "default_slot": "any"}
    try:
        return json.loads(row.get("prefs_json") or "{}") or {}
    except Exception:
        return {}


def set_prefs(user_id: int, patch: dict[str, Any]) -> dict[str, Any]:
    import json

    ensure_prefs_table()
    cur = get_prefs(user_id)
    cur.update({k: v for k, v in (patch or {}).items() if v is not None})
    raw = json.dumps(cur, ensure_ascii=False)
    if db.is_postgres():
        db.execute(
            """
            INSERT INTO user_prefs (user_id, prefs_json) VALUES (?, ?)
            ON CONFLICT (user_id) DO UPDATE SET prefs_json = EXCLUDED.prefs_json, updated_at = NOW()
            """,
            (user_id, raw),
        )
    else:
        db.execute(
            """
            INSERT INTO user_prefs (user_id, prefs_json) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET prefs_json = excluded.prefs_json,
              updated_at = datetime('now')
            """,
            (user_id, raw),
        )
    return cur
