"""Propose folder structure, persist classification rules, apply to new videos."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from typing import Any

from backend import db, llm, youtube as yt

_TOKEN = re.compile(r"[a-zA-Zа-яА-ЯёЁ0-9]{3,}", re.UNICODE)
_STOP = {
    "the",
    "and",
    "для",
    "как",
    "это",
    "что",
    "you",
    "with",
    "from",
    "official",
    "video",
    "music",
}


def ensure_classify_tables() -> None:
    if db.is_postgres():
        stmts = [
            """
            CREATE TABLE IF NOT EXISTS classify_rules (
              id SERIAL PRIMARY KEY,
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              list_id INTEGER NOT NULL REFERENCES lists(id) ON DELETE CASCADE,
              rule_type TEXT NOT NULL,
              rule_value TEXT NOT NULL DEFAULT '',
              priority INTEGER NOT NULL DEFAULT 100,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_classify_rules_user ON classify_rules(user_id, priority)",
        ]
    else:
        stmts = [
            """
            CREATE TABLE IF NOT EXISTS classify_rules (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              list_id INTEGER NOT NULL REFERENCES lists(id) ON DELETE CASCADE,
              rule_type TEXT NOT NULL,
              rule_value TEXT NOT NULL DEFAULT '',
              priority INTEGER NOT NULL DEFAULT 100,
              created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_classify_rules_user ON classify_rules(user_id, priority)",
        ]
    for stmt in stmts:
        try:
            db.execute(stmt)
        except Exception as e:
            msg = str(e).lower()
            if "already exists" in msg or "duplicate" in msg:
                continue
            raise


def _library_snapshot(user_id: int, limit: int = 400) -> list[dict]:
    return db.fetchall(
        """
        SELECT v.video_id, v.title, v.channel_title, v.duration_sec, v.thumb_url,
               li.status, li.source
        FROM library_items li
        JOIN videos v ON v.video_id = li.video_id
        WHERE li.user_id = ?
        ORDER BY li.saved_at DESC
        LIMIT ?
        """,
        (user_id, limit),
    )


def _by_id(rows: list[dict]) -> dict[str, dict]:
    return {r["video_id"]: r for r in rows}


def _preview_items(rows_by_id: dict[str, dict], video_ids: list[str], limit: int = 8) -> list[dict]:
    out = []
    for vid in video_ids[:limit]:
        r = rows_by_id.get(vid)
        if not r:
            continue
        out.append(
            {
                "video_id": vid,
                "title": r.get("title") or vid,
                "channel_title": r.get("channel_title") or "",
                "duration_sec": r.get("duration_sec"),
                "duration_label": yt.format_duration(r.get("duration_sec")),
                "thumb_url": r.get("thumb_url") or yt.thumb_url(vid),
            }
        )
    return out


def _folder(
    title: str,
    reason: str,
    video_ids: list[str],
    *,
    rule: dict | None,
    rows_by_id: dict[str, dict],
    persist: bool = True,
) -> dict[str, Any]:
    return {
        "title": title[:120],
        "reason": reason[:300],
        "video_ids": video_ids,
        "count": len(video_ids),
        "rule": rule,
        "persist": persist and bool(rule),
        "items": _preview_items(rows_by_id, video_ids, 10),
    }


def heuristic_propose(user_id: int) -> dict[str, Any]:
    rows = _library_snapshot(user_id)
    rows_by_id = _by_id(rows)
    by_channel: dict[str, list[str]] = defaultdict(list)
    by_status: dict[str, list[str]] = defaultdict(list)
    shortform: list[str] = []
    longform: list[str] = []
    music: list[str] = []
    tokens: Counter = Counter()

    for r in rows:
        ch = (r.get("channel_title") or "Без канала").strip() or "Без канала"
        vid = r["video_id"]
        bucket = yt.content_bucket(
            r.get("title"),
            ch,
            r.get("duration_sec"),
            None,
        )
        by_status[r.get("status") or "queue"].append(vid)
        if bucket == "music":
            music.append(vid)
            continue
        by_channel[ch].append(vid)
        dur = r.get("duration_sec")
        if isinstance(dur, int):
            if dur <= yt.SHORTFORM_MAX_SEC:
                shortform.append(vid)
            elif dur >= 40 * 60:
                longform.append(vid)
        for t in _TOKEN.findall(r.get("title") or ""):
            tokens[t.lower()] += 1

    folders: list[dict] = []
    queue = by_status.get("queue") or []
    watched = by_status.get("watched") or []
    started = by_status.get("in_progress") or []

    if queue:
        folders.append(
            _folder(
                "В очереди / не разобрано",
                "Черновик: всё ещё в статусе очереди (не правило для новых)",
                queue[:80],
                rule=None,
                rows_by_id=rows_by_id,
                persist=False,
            )
        )
    if music:
        folders.append(
            _folder(
                "Музыка / клипы",
                "Topic, VEVO и клипы — отдельно от плана длинных роликов",
                music[:80],
                rule={"type": "content_kind", "value": "music"},
                rows_by_id=rows_by_id,
                persist=True,
            )
        )
    if shortform:
        folders.append(
            _folder(
                "Короткие (до 6 мин)",
                "Шлак для планирования — не основная очередь",
                shortform[:80],
                rule={"type": "duration_lte", "value": str(yt.SHORTFORM_MAX_SEC)},
                rows_by_id=rows_by_id,
                persist=True,
            )
        )
    if longform:
        folders.append(
            _folder(
                "Длинные (40+ мин)",
                "Нужен слот времени",
                longform[:60],
                rule={"type": "duration_gte", "value": str(40 * 60)},
                rows_by_id=rows_by_id,
                persist=True,
            )
        )

    top_ch = sorted(by_channel.items(), key=lambda x: -len(x[1]))[:10]
    for ch, vids in top_ch:
        if len(vids) < 2 or yt.is_music_channel(ch):
            continue
        folders.append(
            _folder(
                f"Канал: {ch}"[:80],
                f"{len(vids)} видео с этого канала",
                vids[:40],
                rule={"type": "channel", "value": ch},
                rows_by_id=rows_by_id,
                persist=True,
            )
        )

    for word, cnt in tokens.most_common(16):
        if cnt < 3 or word in _STOP:
            continue
        vids = [r["video_id"] for r in rows if word in (r.get("title") or "").lower()][:40]
        if len(vids) < 3:
            continue
        folders.append(
            _folder(
                f"Тема: {word}",
                f"Часто в названиях ({cnt})",
                vids,
                rule={"type": "keyword", "value": word},
                rows_by_id=rows_by_id,
                persist=True,
            )
        )
        if len(folders) >= 18:
            break

    if started:
        folders.append(
            _folder(
                "Начатые",
                "Уже открывал / отметил начатым",
                started[:60],
                rule=None,
                rows_by_id=rows_by_id,
                persist=False,
            )
        )
    if watched:
        folders.append(
            _folder(
                "Уже смотрел",
                "Takeout / отмеченные вручную",
                watched[:60],
                rule=None,
                rows_by_id=rows_by_id,
                persist=False,
            )
        )

    persist_n = sum(1 for f in folders if f.get("persist"))
    return {
        "engine": "heuristic",
        "summary": (
            f"В выборке {len(rows)} видео. Папок с правилами: {persist_n}. "
            "Нажми папку — увидишь ролики. «ОК» сохранит папки и правила для новых ссылок."
        ),
        "folders": folders[:18],
        "limitations": [
            "Watch Later и % просмотра Google API не отдаёт",
            "История — через Takeout",
        ],
    }


def llm_propose(user_id: int) -> dict[str, Any] | None:
    if not llm.available():
        return None
    rows = _library_snapshot(user_id, limit=80)
    if len(rows) < 3:
        return None
    rows_by_id = _by_id(rows)
    compact = [
        {
            "id": r["video_id"],
            "title": (r.get("title") or "")[:120],
            "channel": (r.get("channel_title") or "")[:80],
            "status": r.get("status"),
            "minutes": int((r.get("duration_sec") or 0) / 60) if r.get("duration_sec") else None,
        }
        for r in rows
    ]
    data = llm.chat_json(
        system=(
            "Ты помогаешь разобрать личную библиотеку YouTube-видео. "
            "Ответ JSON: {\"summary\": string, \"folders\": [{\"title\", \"reason\", \"video_ids\": [], "
            "\"rule\": {\"type\": \"channel|keyword|duration_lte|duration_gte\", \"value\": string}}]}. "
            "6–12 папок. video_ids только из входного списка."
        ),
        user=json.dumps(compact, ensure_ascii=False),
        temperature=0.3,
        timeout=10,
        max_models=1,
    )
    if not data:
        return None
    valid_ids = {x["id"] for x in compact}
    folders = []
    for f in data.get("folders") or []:
        vids = [v for v in (f.get("video_ids") or []) if v in valid_ids]
        if not vids:
            continue
        rule = f.get("rule") if isinstance(f.get("rule"), dict) else None
        folders.append(
            _folder(
                str(f.get("title") or "Папка"),
                str(f.get("reason") or ""),
                vids[:50],
                rule=rule,
                rows_by_id=rows_by_id,
                persist=bool(rule),
            )
        )
    if not folders:
        return None
    return {
        "engine": "llm",
        "summary": str(data.get("summary") or "")[:800],
        "folders": folders[:16],
        "limitations": ["Нет официального доступа к Watch Later и Continue Watching"],
    }


def propose_structure(user_id: int, *, use_llm: bool = False) -> dict[str, Any]:
    ensure_classify_tables()
    proposal = None
    if use_llm:
        proposal = llm_propose(user_id)
    if not proposal:
        proposal = heuristic_propose(user_id)
    db.execute(
        "INSERT INTO organize_proposals (user_id, proposal_json) VALUES (?, ?)",
        (user_id, json.dumps(proposal, ensure_ascii=False)),
    )
    row = db.fetchone(
        "SELECT id FROM organize_proposals WHERE user_id = ? ORDER BY id DESC LIMIT 1",
        (user_id,),
    )
    proposal["proposal_id"] = int(row["id"]) if row else None
    return proposal


def _ensure_list(user_id: int, title: str) -> int:
    existing = db.fetchone(
        "SELECT id FROM lists WHERE user_id = ? AND title = ?",
        (user_id, title),
    )
    if existing:
        return int(existing["id"])
    if db.is_postgres():
        with db.connect() as conn:
            cur = conn.execute(
                "INSERT INTO lists (user_id, title) VALUES (%s, %s) RETURNING id",
                (user_id, title),
            )
            return int(cur.fetchone()["id"])
    db.execute("INSERT INTO lists (user_id, title) VALUES (?, ?)", (user_id, title))
    return int(
        db.fetchone(
            "SELECT id FROM lists WHERE user_id = ? AND title = ?",
            (user_id, title),
        )["id"]
    )


def _add_list_item(list_id: int, video_id: str, position: int = 0) -> None:
    db.execute(
        "INSERT INTO list_items (list_id, video_id, position) VALUES (?, ?, ?) "
        + (
            "ON CONFLICT DO NOTHING"
            if db.is_postgres()
            else "ON CONFLICT(list_id, video_id) DO NOTHING"
        ),
        (list_id, video_id, position),
    )


def apply_proposal(user_id: int, proposal: dict) -> dict[str, Any]:
    """Create lists, put videos, SAVE classification rules for future shares."""
    ensure_classify_tables()
    # Replace previous auto-rules for this user (keep lists)
    db.execute("DELETE FROM classify_rules WHERE user_id = ?", (user_id,))

    created = []
    rules_saved = 0
    priority = 10
    for folder in proposal.get("folders") or []:
        title = (folder.get("title") or "").strip()[:120]
        vids = folder.get("video_ids") or []
        if not title or not vids:
            continue
        list_id = _ensure_list(user_id, title)
        n = 0
        for vid in vids:
            _add_list_item(list_id, vid, n)
            n += 1
        rule = folder.get("rule") if folder.get("persist", True) else None
        if isinstance(rule, dict) and rule.get("type"):
            db.execute(
                "INSERT INTO classify_rules (user_id, list_id, rule_type, rule_value, priority) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    user_id,
                    list_id,
                    str(rule.get("type"))[:40],
                    str(rule.get("value") or "")[:200],
                    priority,
                ),
            )
            rules_saved += 1
            priority += 10
        created.append(
            {
                "id": list_id,
                "title": title,
                "count": n,
                "persist": bool(rule),
                "rule": rule,
            }
        )
    return {
        "ok": True,
        "lists": created,
        "rules_saved": rules_saved,
    }


def list_rules(user_id: int) -> list[dict]:
    ensure_classify_tables()
    rows = db.fetchall(
        """
        SELECT r.*, l.title AS list_title
        FROM classify_rules r
        JOIN lists l ON l.id = r.list_id
        WHERE r.user_id = ?
        ORDER BY r.priority ASC, r.id ASC
        """,
        (user_id,),
    )
    return [
        {
            "id": r["id"],
            "list_id": r["list_id"],
            "list_title": r.get("list_title"),
            "rule_type": r.get("rule_type"),
            "rule_value": r.get("rule_value"),
            "priority": r.get("priority"),
        }
        for r in rows
    ]


def match_rules_for_video(
    user_id: int,
    *,
    title: str | None,
    channel_title: str | None,
    duration_sec: int | None,
) -> list[dict]:
    """Return matching saved lists for a video (does not write)."""
    rules = list_rules(user_id)
    if not rules:
        return []
    title_l = (title or "").lower()
    channel = (channel_title or "").strip()
    bucket = yt.content_bucket(title, channel_title, duration_sec, None)
    matched = []
    seen = set()
    for r in rules:
        rtype = r.get("rule_type")
        val = r.get("rule_value") or ""
        ok = False
        if rtype == "channel" and channel and channel == val:
            ok = True
        elif rtype == "keyword" and val and val.lower() in title_l:
            ok = True
        elif rtype == "duration_lte":
            try:
                ok = duration_sec is not None and int(duration_sec) <= int(val)
            except ValueError:
                ok = False
        elif rtype == "duration_gte":
            try:
                ok = duration_sec is not None and int(duration_sec) >= int(val)
            except ValueError:
                ok = False
        elif rtype == "content_kind" and bucket == val:
            ok = True
        if ok and r["list_id"] not in seen:
            seen.add(r["list_id"])
            matched.append(r)
    return matched


def apply_rules_to_video(
    user_id: int,
    video_id: str,
    *,
    title: str | None = None,
    channel_title: str | None = None,
    duration_sec: int | None = None,
) -> list[dict]:
    """Put video into matching lists from saved classification."""
    if title is None or channel_title is None or duration_sec is None:
        row = db.fetchone("SELECT * FROM videos WHERE video_id = ?", (video_id,))
        if row:
            title = title if title is not None else row.get("title")
            channel_title = (
                channel_title if channel_title is not None else row.get("channel_title")
            )
            duration_sec = (
                duration_sec if duration_sec is not None else row.get("duration_sec")
            )
    matched = match_rules_for_video(
        user_id,
        title=title,
        channel_title=channel_title,
        duration_sec=duration_sec,
    )
    for m in matched:
        _add_list_item(int(m["list_id"]), video_id, 0)
    return matched
