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
    "partner": {
        "label": "С партнёром",
        "hint": "удобно смотреть вдвоём",
        "keywords": (
            "фильм", "сериал", "movie", "кино", "вдвоём", "пароч", "роман",
            "комедия", "thriller", "драм",
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
    """Heuristic nudges with explicit why: continue, ~40m, stale folder, short win."""
    out: list[dict] = []

    # Continue started
    for r in pool:
        if r["video_id"] in exclude:
            continue
        if r.get("status") == "in_progress":
            out.append(_card(r, reason="Продолжить начатое"))
            exclude.add(r["video_id"])
            break

    # ~40 minute slot
    for r in pool:
        if r["video_id"] in exclude:
            continue
        dur = r.get("duration_sec")
        if isinstance(dur, int) and 30 * 60 <= dur <= 50 * 60:
            out.append(_card(r, reason="У вас ~40 минут — как раз этот ролик"))
            exclude.add(r["video_id"])
            break

    # High interest not started
    for r in pool:
        if r["video_id"] in exclude:
            continue
        if int(r.get("interest") or 0) >= 1 and r.get("status") == "queue":
            out.append(_card(r, reason="Вы хотели это посмотреть"))
            exclude.add(r["video_id"])
            break

    # Stale thematic folder: pick from list with few recent opens
    stale = _stale_folder_pick(user_id, exclude)
    if stale:
        out.append(stale)
        exclude.add(stale["video_id"])

    # Short win
    for r in pool:
        if len(out) >= limit:
            break
        if r["video_id"] in exclude:
            continue
        dur = r.get("duration_sec")
        if isinstance(dur, int) and 3 * 60 <= dur <= 12 * 60:
            out.append(_card(r, reason="Короткий слот — можно сейчас"))
            exclude.add(r["video_id"])
            break

    # With personal note / lexicon
    for r in pool:
        if len(out) >= limit:
            break
        if r["video_id"] in exclude:
            continue
        if (r.get("note") or "").strip():
            out.append(_card(r, reason="По вашей формулировке"))
            exclude.add(r["video_id"])
            break

    # Fallback
    for r in pool:
        if len(out) >= limit:
            break
        if r["video_id"] in exclude:
            continue
        out.append(_card(r, reason="Из вашей очереди"))
        exclude.add(r["video_id"])
    return out[:limit]


def _stale_folder_pick(user_id: int, exclude: set[str]) -> Optional[dict]:
    """Video from a thematic folder that hasn't been opened recently."""
    folders = db.fetchall(
        """
        SELECT l.id, l.title, COUNT(li.video_id) AS c
        FROM lists l
        JOIN list_items li ON li.list_id = l.id
        WHERE l.user_id = ?
          AND l.title NOT LIKE 'YT:%'
          AND lower(l.title) NOT LIKE '%скрыто%'
        GROUP BY l.id, l.title
        HAVING COUNT(li.video_id) >= 2
        ORDER BY c DESC
        LIMIT 12
        """,
        (user_id,),
    )
    for f in folders:
        lid = int(f["id"])
        title = (f.get("title") or "папка").strip()
        row = db.fetchone(
            """
            SELECT v.video_id, v.title, v.channel_title, v.duration_sec, v.thumb_url,
                   lib.status, lib.interest, lib.note
            FROM list_items li
            JOIN videos v ON v.video_id = li.video_id
            JOIN library_items lib ON lib.video_id = v.video_id AND lib.user_id = ?
            WHERE li.list_id = ?
              AND lib.status IN ('queue', 'in_progress')
            ORDER BY li.added_at ASC
            LIMIT 8
            """,
            (user_id, lid),
        )
        if not row or row["video_id"] in exclude:
            continue
        if not _eligible(row):
            continue
        return _card(row, reason=f"Давно не заходили в «{title[:40]}»")
    return None


def get_light_plan(user_id: int) -> dict[str, Any]:
    """Ordered tonight/week overlay over queue (stored in prefs)."""
    prefs = get_prefs(user_id)
    plan = prefs.get("light_plan") or {}
    tonight_ids = [str(x) for x in (plan.get("tonight") or []) if x][:12]
    week_ids = [str(x) for x in (plan.get("week") or []) if x][:20]
    return {
        "tonight": _hydrate_ids(user_id, tonight_ids),
        "week": _hydrate_ids(user_id, week_ids),
        "tonight_ids": tonight_ids,
        "week_ids": week_ids,
    }


def set_light_plan(
    user_id: int,
    *,
    tonight: Optional[list[str]] = None,
    week: Optional[list[str]] = None,
) -> dict[str, Any]:
    prefs = get_prefs(user_id)
    plan = dict(prefs.get("light_plan") or {})
    if tonight is not None:
        plan["tonight"] = [str(x) for x in tonight if x][:12]
    if week is not None:
        plan["week"] = [str(x) for x in week if x][:20]
    set_prefs(user_id, {"light_plan": plan})
    return get_light_plan(user_id)


def add_to_light_plan(user_id: int, video_id: str, bucket: str = "tonight") -> dict[str, Any]:
    video_id = (video_id or "").strip()
    if not video_id:
        return get_light_plan(user_id)
    plan = get_light_plan(user_id)
    key = "tonight" if bucket != "week" else "week"
    ids = list(plan.get(f"{key}_ids") or [])
    if video_id in ids:
        ids = [video_id] + [x for x in ids if x != video_id]
    else:
        ids = [video_id] + ids
    if key == "tonight":
        return set_light_plan(user_id, tonight=ids[:12])
    return set_light_plan(user_id, week=ids[:20])


def remove_from_light_plan(user_id: int, video_id: str, bucket: str = "tonight") -> dict[str, Any]:
    video_id = (video_id or "").strip()
    plan = get_light_plan(user_id)
    if bucket == "week":
        ids = [x for x in (plan.get("week_ids") or []) if x != video_id]
        return set_light_plan(user_id, week=ids)
    ids = [x for x in (plan.get("tonight_ids") or []) if x != video_id]
    return set_light_plan(user_id, tonight=ids)


def _hydrate_ids(user_id: int, ids: list[str]) -> list[dict]:
    if not ids:
        return []
    out = []
    for vid in ids:
        row = db.fetchone(
            """
            SELECT v.video_id, v.title, v.channel_title, v.duration_sec, v.thumb_url,
                   li.status, li.interest, li.note
            FROM videos v
            JOIN library_items li ON li.video_id = v.video_id AND li.user_id = ?
            WHERE v.video_id = ?
            """,
            (user_id, vid),
        )
        if row:
            out.append(_card(row, reason="В вашем плане"))
    return out


def inbox_onboarding_status(user_id: int) -> dict[str, Any]:
    """Product contract: detect спецпапка (Listen later / смотреть позже)."""
    from backend.yt_sync import is_inbox_playlist_title

    lists = db.fetchall(
        "SELECT id, title FROM lists WHERE user_id = ? ORDER BY id ASC",
        (user_id,),
    )
    inbox = []
    for r in lists:
        title = r.get("title") or ""
        if is_inbox_playlist_title(title) or is_inbox_playlist_title(title.replace("YT: ", "", 1)):
            inbox.append({"id": int(r["id"]), "title": title})
    prefs = get_prefs(user_id)
    return {
        "has_inbox": bool(inbox),
        "inbox_lists": inbox,
        "primary": inbox[0] if inbox else None,
        "onboarding_done": bool(prefs.get("inbox_onboarding_done")),
        "hint": (
            "Ваша спецпапка — плейлист вроде «смотреть позже» или Listen later. "
            "С него Kyro берёт желаемое для блока «Сейчас»."
            if not inbox
            else f"Спецпапка: {(inbox[0].get('title') or '').replace('YT: ', '', 1)}"
        ),
    }


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
        return {"digest_enabled": True, "default_slot": "any", "quiet_start": 23, "quiet_end": 8}
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
