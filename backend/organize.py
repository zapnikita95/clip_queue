"""Propose folder structure, persist classification rules, apply to new videos."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from typing import Any

from backend import db, llm, themes, youtube as yt

_TOKEN = re.compile(r"[a-zA-Zа-яА-ЯёЁ0-9]{4,}", re.UNICODE)
_STOP = {
    "the",
    "and",
    "with",
    "from",
    "this",
    "that",
    "your",
    "для",
    "как",
    "это",
    "что",
    "или",
    "видео",
    "video",
    "official",
    "full",
    "watch",
    "часть",
    "выпуск",
    "сериал",
    "фильм",
    "private",
    "deleted",
    "shorts",
    "short",
    "hippie",
    "topic",
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
        "items": _preview_items(rows_by_id, video_ids, 14),
    }


def heuristic_propose(user_id: int) -> dict[str, Any]:
    rows = _library_snapshot(user_id)
    rows_by_id = _by_id(rows)
    by_channel: dict[str, list[str]] = defaultdict(list)
    by_status: dict[str, list[str]] = defaultdict(list)
    shortform: list[str] = []
    longform: list[str] = []
    music: list[str] = []

    music_ids: set[str] = set()
    shortform_ids: set[str] = set()
    for r in rows:
        ch = (r.get("channel_title") or "Без канала").strip() or "Без канала"
        vid = r["video_id"]
        bucket = yt.content_bucket(
            r.get("title"),
            ch,
            r.get("duration_sec"),
            None,
        )
        if yt.is_unavailable_video(r.get("title")):
            continue
        # Music never enters planning folders / unsorted draft.
        if bucket == "music":
            music.append(vid)
            music_ids.add(vid)
            continue
        # Shorts / ≤6 min — archive from queue; never themes / channel folders
        if bucket in ("shorts", "shortform") or (
            isinstance(r.get("duration_sec"), int)
            and 0 < int(r.get("duration_sec")) <= yt.SHORTFORM_MAX_SEC
        ):
            shortform.append(vid)
            shortform_ids.add(vid)
            continue
        by_status[r.get("status") or "queue"].append(vid)
        by_channel[ch].append(vid)
        dur = r.get("duration_sec")
        if isinstance(dur, int) and dur >= 40 * 60:
            longform.append(vid)

    folders: list[dict] = []
    queue = by_status.get("queue") or []
    watched = by_status.get("watched") or []
    started = by_status.get("in_progress") or []

    # --- Themes first (what the user actually wants to browse) ---
    by_theme: dict[str, list[str]] = defaultdict(list)
    themed_ids: set[str] = set()
    for r in rows:
        vid = r["video_id"]
        if vid in music_ids or vid in shortform_ids:
            continue
        if yt.is_unavailable_video(r.get("title")):
            continue
        primary = themes.primary_theme(r.get("title"), r.get("channel_title"))
        if not primary:
            continue
        by_theme[primary["id"]].append(vid)
        themed_ids.add(vid)

    theme_folders = []
    for theme_def in themes.THEMES:
        tid = theme_def["id"]
        vids = by_theme.get(tid) or []
        if len(vids) < 2:
            continue
        theme_folders.append(
            _folder(
                theme_def["title"],
                f"Тема · {len(vids)} видео (по названию и каналу)",
                vids[:60],
                rule={"type": "theme", "value": tid},
                rows_by_id=rows_by_id,
                persist=True,
            )
        )
    # Biggest themes first
    theme_folders.sort(key=lambda f: -int(f.get("count") or 0))
    folders.extend(theme_folders)

    # Personal keyword themes from THIS user's titles (not only shared taxonomy)
    token_hits: Counter = Counter()
    token_vids: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        vid = r["video_id"]
        if vid in music_ids or vid in themed_ids:
            continue
        seen_tok = set()
        for tok in _TOKEN.findall((r.get("title") or "").lower()):
            if tok in _STOP or tok in seen_tok:
                continue
            seen_tok.add(tok)
            token_hits[tok] += 1
            if len(token_vids[tok]) < 40:
                token_vids[tok].append(vid)
    personal = []
    for word, cnt in token_hits.most_common(20):
        vids = token_vids.get(word) or []
        if cnt < 3 or len(vids) < 3:
            continue
        # skip if overlaps a taxonomy theme title word
        personal.append(
            _folder(
                f"Тема: {word}",
                f"Из твоих названий · {cnt} совпадений (личная тема)",
                vids,
                rule={"type": "keyword", "value": word},
                rows_by_id=rows_by_id,
                persist=True,
            )
        )
        for v in vids:
            themed_ids.add(v)
        if len(personal) >= 5:
            break
    folders.extend(personal)

    # Shorts/≤6min: purged from queue above; do NOT create a planning list/rule.
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

    # Channels only as secondary (skip if almost everything already themed)
    top_ch = sorted(by_channel.items(), key=lambda x: -len(x[1]))[:6]
    for ch, vids in top_ch:
        if len(vids) < 3 or yt.is_music_channel(ch):
            continue
        # Prefer theme coverage — skip channel if ≤1 video outside themes
        unthemed = [v for v in vids if v not in themed_ids]
        if len(unthemed) < 2 and len(vids) <= 5:
            continue
        folders.append(
            _folder(
                f"Канал: {ch}"[:80],
                f"{len(vids)} видео с канала (доп. к тематикам)",
                vids[:40],
                rule={"type": "channel", "value": ch},
                rows_by_id=rows_by_id,
                persist=True,
            )
        )

    # Leftover queue without a theme — useful “ещё не размечено”
    unthemed_queue = [v for v in queue if v not in themed_ids] if queue else []
    if unthemed_queue:
        folders.append(
            _folder(
                "Без темы / разобрать",
                "В очереди, но авто-тема не сработала — кликни и глянь",
                unthemed_queue[:80],
                rule=None,
                rows_by_id=rows_by_id,
                persist=False,
            )
        )

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
            f"В выборке {len(rows)} · тем: {len(theme_folders)} · "
            f"личных: {len(personal)} · без темы: {len(unthemed_queue)} · "
            f"музыка: {len(music_ids)} · короткие ≤6м: {len(shortform_ids)}. "
            "Темы и каналы — только нормальные видео 6м–10ч. "
            "«ОК» сохранит правила для новых ссылок."
        ),
        "folders": folders[:22],
        "music_hidden": len(music_ids),
        "shortform_hidden": len(shortform_ids),
        "music_ids": list(music_ids)[:500],
        "personalized": True,
        "limitations": [
            "Темы + каналы только для видео длиннее 6 минут",
            "Музыка и короткие убраны из плана",
            "Watch Later (WL) Google API не отдаёт — только лайки и обычные плейлисты",
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
    # Kick music + broken stubs out of planning immediately.
    broken = purge_unavailable(user_id)
    purged = purge_music_from_queue(user_id)
    short_purged = purge_shortform_from_queue(user_id)
    proposal = None
    if use_llm:
        proposal = llm_propose(user_id)
    if not proposal:
        proposal = heuristic_propose(user_id)
    proposal["music_purged"] = purged
    proposal["broken_purged"] = broken
    proposal["shortform_purged"] = short_purged
    db.execute(
        "INSERT INTO organize_proposals (user_id, proposal_json) VALUES (?, ?)",
        (user_id, json.dumps({k: v for k, v in proposal.items() if k != "music_ids"}, ensure_ascii=False)),
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


def purge_unavailable(user_id: int) -> int:
    """Remove private/deleted stubs from planning library."""
    rows = db.fetchall(
        """
        SELECT li.video_id
        FROM library_items li
        JOIN videos v ON v.video_id = li.video_id
        WHERE li.user_id = ?
        """,
        (user_id,),
    )
    n = 0
    for r in rows:
        vid = r["video_id"]
        title_row = db.fetchone("SELECT title FROM videos WHERE video_id = ?", (vid,))
        title = (title_row or {}).get("title")
        if not yt.is_unavailable_video(title):
            continue
        db.execute(
            "DELETE FROM list_items WHERE video_id = ? AND list_id IN "
            "(SELECT id FROM lists WHERE user_id = ?)",
            (vid, user_id),
        )
        db.execute(
            "DELETE FROM item_tags WHERE user_id = ? AND video_id = ?",
            (user_id, vid),
        )
        db.execute(
            "DELETE FROM library_items WHERE user_id = ? AND video_id = ?",
            (user_id, vid),
        )
        n += 1
    return n


def purge_music_from_queue(user_id: int, video_ids: list[str] | None = None) -> int:
    """Kick music/clips out of planning queue → archived."""
    if video_ids is None:
        rows = _library_snapshot(user_id, limit=2000)
        video_ids = [
            r["video_id"]
            for r in rows
            if yt.content_bucket(
                r.get("title"),
                r.get("channel_title"),
                r.get("duration_sec"),
                None,
            )
            == "music"
            and (r.get("status") or "") in ("queue", "in_progress")
        ]
    n = 0
    for vid in video_ids:
        db.execute(
            "UPDATE library_items SET status = 'archived' "
            "WHERE user_id = ? AND video_id = ? AND status IN ('queue', 'in_progress')",
            (user_id, vid),
        )
        n += 1
    return n


def purge_shortform_from_queue(user_id: int) -> int:
    """≤6 min / shorts leave the planning queue (still in library as archived)."""
    rows = _library_snapshot(user_id, limit=2000)
    n = 0
    for r in rows:
        if (r.get("status") or "") not in ("queue", "in_progress"):
            continue
        bucket = yt.content_bucket(
            r.get("title"),
            r.get("channel_title"),
            r.get("duration_sec"),
            None,
        )
        if bucket not in ("shorts", "shortform"):
            continue
        db.execute(
            "UPDATE library_items SET status = 'archived' "
            "WHERE user_id = ? AND video_id = ? AND status IN ('queue', 'in_progress')",
            (user_id, r["video_id"]),
        )
        n += 1
    return n


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
        # Replace membership so edits (move between folders) stick
        db.execute("DELETE FROM list_items WHERE list_id = ?", (list_id,))
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

    music_purged = purge_music_from_queue(
        user_id,
        list(proposal.get("music_ids") or []) or None,
    )
    # Keep a rule so future shares of music don't stay in the planning queue
    music_list_id = _ensure_list(user_id, "Музыка / клипы (скрыто)")
    db.execute(
        "INSERT INTO classify_rules (user_id, list_id, rule_type, rule_value, priority) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, music_list_id, "content_kind", "music", 1),
    )
    rules_saved += 1

    return {
        "ok": True,
        "lists": created,
        "rules_saved": rules_saved,
        "music_purged": music_purged,
    }


_SKIP_LIST_TITLES = {
    "лайки youtube",
    "музыка / клипы (скрыто)",
    "музыка / клипы",
}


def _is_sync_dump_list(title: str) -> bool:
    t = (title or "").strip()
    if not t:
        return True
    low = t.lower()
    if low in _SKIP_LIST_TITLES:
        return True
    if t.startswith("YT:"):
        return True
    return False


def saved_structure(user_id: int, *, items_per_folder: int = 24) -> dict[str, Any]:
    """Load the user's last saved organize folders from lists (+ rules)."""
    ensure_classify_tables()
    rules = list_rules(user_id)
    rules_by_list: dict[int, dict] = {}
    for r in rules:
        lid = int(r["list_id"])
        if lid not in rules_by_list:
            rules_by_list[lid] = {
                "type": r.get("rule_type"),
                "value": r.get("rule_value") or "",
            }

    lists = db.fetchall(
        "SELECT * FROM lists WHERE user_id = ? ORDER BY id ASC",
        (user_id,),
    )
    folders: list[dict[str, Any]] = []
    for lst in lists:
        title = (lst.get("title") or "").strip()
        if _is_sync_dump_list(title):
            continue
        lid = int(lst["id"])
        # Prefer lists that have classify rules; if none exist yet, still show
        # non-sync lists with videos (manual folders).
        if rules_by_list and lid not in rules_by_list:
            # Skip music hidden even if somehow not caught
            if "скрыто" in title.lower():
                continue
            # Without any theme/channel rule — only keep if user has zero rules
            # (then show nothing meaningful) OR include manual lists
            if rules:
                # Still include channel/theme-looking lists without rule? No —
                # after apply every persist folder has a rule. Orphans = old junk.
                continue

        rows = db.fetchall(
            """
            SELECT v.video_id, v.title, v.channel_title, v.duration_sec, v.thumb_url
            FROM list_items x
            JOIN videos v ON v.video_id = x.video_id
            WHERE x.list_id = ?
            ORDER BY x.position ASC, x.added_at DESC
            LIMIT ?
            """,
            (lid, max(items_per_folder, 80)),
        )
        video_ids = []
        items = []
        for r in rows:
            if yt.is_unavailable_video(r.get("title")):
                continue
            vid = r["video_id"]
            video_ids.append(vid)
            items.append(
                {
                    "video_id": vid,
                    "title": r.get("title") or vid,
                    "channel_title": r.get("channel_title") or "",
                    "duration_sec": r.get("duration_sec"),
                    "duration_label": yt.format_duration(r.get("duration_sec")),
                    "thumb_url": r.get("thumb_url") or yt.thumb_url(vid),
                }
            )
        if not video_ids:
            continue
        rule = rules_by_list.get(lid)
        folders.append(
            {
                "list_id": lid,
                "title": title[:120],
                "reason": "Сохранено",
                "video_ids": video_ids,
                "count": len(video_ids),
                "rule": rule,
                "persist": bool(rule),
                "items": items[:items_per_folder],
            }
        )

    # Fallback: last applied proposal JSON if lists empty but proposal exists
    if not folders:
        row = db.fetchone(
            """
            SELECT id, proposal_json FROM organize_proposals
            WHERE user_id = ? AND applied = 1
            ORDER BY id DESC LIMIT 1
            """,
            (user_id,),
        )
        if row:
            try:
                proposal = json.loads(row["proposal_json"] or "{}")
            except Exception:
                proposal = {}
            for f in proposal.get("folders") or []:
                if not f.get("video_ids"):
                    continue
                folders.append(
                    {
                        "list_id": None,
                        "title": (f.get("title") or "")[:120],
                        "reason": f.get("reason") or "Из прошлого сохранения",
                        "video_ids": list(f.get("video_ids") or []),
                        "count": len(f.get("video_ids") or []),
                        "rule": f.get("rule"),
                        "persist": bool(f.get("persist", True)),
                        "items": (f.get("items") or [])[:items_per_folder],
                    }
                )

    theme_opts = [
        {"id": t["id"], "title": t["title"]}
        for t in themes.THEMES
    ]
    return {
        "has_structure": bool(folders),
        "folders": folders,
        "rules_count": len(rules),
        "summary": (
            f"Сохранено папок: {len(folders)} · правил: {len(rules)}"
            if folders
            else "Раскладки ещё нет — нажми «Разложить» один раз и сохрани."
        ),
        "themes": theme_opts,
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
        elif rtype == "theme" and val:
            ok = themes.matches_theme(val, title, channel)
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
