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
        SELECT v.video_id, v.title, v.channel_title, v.duration_sec, v.thumb_url, v.description,
               li.status, li.source
        FROM library_items li
        JOIN videos v ON v.video_id = li.video_id
        WHERE li.user_id = ?
          AND li.status NOT IN ('dismissed', 'archived')
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

    # --- Themes first (multi-theme OK if scores are close) ---
    by_theme: dict[str, list[str]] = defaultdict(list)
    themed_ids: set[str] = set()
    for r in rows:
        vid = r["video_id"]
        if vid in music_ids or vid in shortform_ids:
            continue
        if yt.is_unavailable_video(r.get("title")):
            continue
        found = themes.detect_themes(
            r.get("title"),
            r.get("channel_title"),
            description=r.get("description"),
            min_score=3,
        )
        if not found:
            continue
        # Primary always; second theme if score within 2 of primary and >= 4
        top = found[:1]
        if len(found) > 1:
            # re-score to compare
            s0 = themes.score_theme(
                found[0], r.get("title") or "", r.get("channel_title") or "", r.get("description") or ""
            )
            s1 = themes.score_theme(
                found[1], r.get("title") or "", r.get("channel_title") or "", r.get("description") or ""
            )
            if s1 >= 4 and s0 - s1 <= 2:
                top = found[:2]
        for th in top:
            if vid not in by_theme[th["id"]]:
                by_theme[th["id"]].append(vid)
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
    for fi, folder in enumerate(proposal.get("folders") or []):
        title = (folder.get("title") or "").strip()[:120]
        vids = folder.get("video_ids") or []
        if not title or not vids:
            continue
        list_id = _ensure_list(user_id, title)
        db.execute(
            "UPDATE lists SET sort_order = ? WHERE id = ? AND user_id = ?",
            (fi * 10, list_id, user_id),
        )
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
        "SELECT * FROM lists WHERE user_id = ? ORDER BY sort_order ASC, id ASC",
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
            SELECT v.video_id, v.title, v.channel_title, v.duration_sec, v.thumb_url,
                   COALESCE(li.interest, 0) AS interest
            FROM list_items x
            JOIN videos v ON v.video_id = x.video_id
            LEFT JOIN library_items li
              ON li.video_id = x.video_id AND li.user_id = ?
            WHERE x.list_id = ?
              AND COALESCE(li.status, 'queue') NOT IN ('dismissed', 'rejected')
            ORDER BY COALESCE(li.interest, 0) DESC, x.position ASC, x.added_at DESC
            LIMIT ?
            """,
            (user_id, lid, max(items_per_folder, 80)),
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
                    "interest": int(r.get("interest") or 0),
                    "watch_url": f"https://www.youtube.com/watch?v={vid}",
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


_CATCHALL_LIST_MARKERS = (
    "без темы",
    "разобрать",
    "не разобрано",
    "в очереди /",
)


def _is_catchall_list_title(title: str) -> bool:
    low = (title or "").strip().lower()
    if not low:
        return False
    return any(m in low for m in _CATCHALL_LIST_MARKERS)


def _themed_list_ids(user_id: int) -> set[int]:
    """Lists that count as «разобрано» (theme / channel / keyword / theme rules)."""
    out: set[int] = set()
    for r in list_rules(user_id):
        rtype = r.get("rule_type") or ""
        title = r.get("list_title") or ""
        if _is_catchall_list_title(title) or "скрыто" in title.lower():
            continue
        if rtype in ("theme", "channel", "keyword"):
            out.add(int(r["list_id"]))
    theme_titles = {t["title"].strip().lower() for t in themes.THEMES}
    for lst in db.fetchall(
        "SELECT id, title FROM lists WHERE user_id = ?", (user_id,)
    ):
        t = (lst.get("title") or "").strip().lower()
        if not t or _is_catchall_list_title(t) or "скрыто" in t:
            continue
        if t in theme_titles or t.startswith("канал:") or t.startswith("тема:"):
            out.add(int(lst["id"]))
    return out


def _catchall_list_ids(user_id: int) -> list[int]:
    return [
        int(r["id"])
        for r in db.fetchall("SELECT id, title FROM lists WHERE user_id = ?", (user_id,))
        if _is_catchall_list_title(r.get("title") or "")
    ]


def _remove_from_catchall(user_id: int, video_id: str) -> None:
    for lid in _catchall_list_ids(user_id):
        db.execute(
            "DELETE FROM list_items WHERE list_id = ? AND video_id = ?",
            (lid, video_id),
        )


def _match_theme_folders(
    user_id: int,
    video_id: str,
    *,
    title: str | None,
    channel_title: str | None,
    description: str | None,
) -> list[dict]:
    """Put video into existing folders whose titles match detected themes."""
    detected = themes.detect_themes(
        title, channel_title, description=description or "", min_score=3
    )
    if not detected:
        return []
    lists = {
        (r.get("title") or "").strip().lower(): r
        for r in db.fetchall(
            "SELECT id, title FROM lists WHERE user_id = ?", (user_id,)
        )
    }
    matched: list[dict] = []
    seen: set[int] = set()
    for th in detected:
        key = (th.get("title") or "").strip().lower()
        lst = lists.get(key)
        if not lst:
            continue
        lid = int(lst["id"])
        if lid in seen:
            continue
        seen.add(lid)
        _add_list_item(lid, video_id, 0)
        matched.append(
            {
                "list_id": lid,
                "list_title": lst.get("title"),
                "rule_type": "theme",
                "rule_value": th.get("id") or "",
            }
        )
    return matched


def pending_to_classify(user_id: int, *, limit: int = 250) -> list[dict[str, Any]]:
    """Queue videos not yet in a themed folder (background sync backlog)."""
    ensure_classify_tables()
    themed_ids = _themed_list_ids(user_id)
    classified_vids: set[str] = set()
    if themed_ids:
        placeholders = ",".join("?" * len(themed_ids))
        rows = db.fetchall(
            f"SELECT DISTINCT video_id FROM list_items WHERE list_id IN ({placeholders})",
            tuple(themed_ids),
        )
        classified_vids = {r["video_id"] for r in rows}

    lib = db.fetchall(
        """
        SELECT v.video_id, v.title, v.channel_title, v.duration_sec, v.thumb_url, li.saved_at
        FROM library_items li
        JOIN videos v ON v.video_id = li.video_id
        WHERE li.user_id = ?
          AND li.status IN ('queue', 'in_progress')
        ORDER BY li.saved_at DESC
        LIMIT ?
        """,
        (user_id, max(limit * 4, 400)),
    )
    out: list[dict[str, Any]] = []
    for r in lib:
        vid = r["video_id"]
        if vid in classified_vids:
            continue
        if yt.is_unavailable_video(r.get("title")):
            continue
        bucket = yt.content_bucket(
            r.get("title"), r.get("channel_title"), r.get("duration_sec"), None
        )
        if bucket in ("music", "shorts", "shortform", "unavailable"):
            continue
        out.append(
            {
                "video_id": vid,
                "title": r.get("title") or vid,
                "channel_title": r.get("channel_title") or "",
                "duration_sec": r.get("duration_sec"),
                "thumb_url": r.get("thumb_url") or yt.thumb_url(vid),
                "saved_at": str(r.get("saved_at") or ""),
            }
        )
        if len(out) >= limit:
            break
    return out


def classify_new_video(
    user_id: int,
    video_id: str,
    *,
    title: str | None = None,
    channel_title: str | None = None,
    duration_sec: int | None = None,
    description: str | None = None,
    use_llm: bool = True,
) -> dict[str, Any]:
    """Rules → theme folders → optional LLM into existing folders."""
    row = db.fetchone("SELECT * FROM videos WHERE video_id = ?", (video_id,))
    if row:
        title = title if title is not None else row.get("title")
        channel_title = channel_title if channel_title is not None else row.get("channel_title")
        duration_sec = duration_sec if duration_sec is not None else row.get("duration_sec")
        description = description if description is not None else row.get("description")

    matched = apply_rules_to_video(
        user_id,
        video_id,
        title=title,
        channel_title=channel_title,
        duration_sec=duration_sec,
    )
    # Real folders (not just «длинные» / music dump)
    theme_like = [
        m
        for m in matched
        if (m.get("rule_type") or "") in ("theme", "channel", "keyword")
        or (
            (m.get("rule_type") or "") == "content_kind"
            and (m.get("rule_value") or "") != "music"
        )
    ]
    if not theme_like:
        theme_hits = _match_theme_folders(
            user_id,
            video_id,
            title=title,
            channel_title=channel_title,
            description=description,
        )
        theme_like = theme_hits
        matched = list(matched) + theme_hits

    if theme_like:
        _remove_from_catchall(user_id, video_id)
        eng = "rules"
        if all((m.get("rule_type") or "") == "theme" for m in theme_like):
            eng = "themes"
        return {
            "matched": theme_like,
            "engine": eng,
            "reason": "Совпадение с правилами / темами",
        }

    if not use_llm:
        return {"matched": [], "engine": "none", "reason": "Нет совпадения (без LLM)"}

    rules = [
        r
        for r in list_rules(user_id)
        if (r.get("list_title") or "")
        and "скрыто" not in (r.get("list_title") or "").lower()
        and not _is_catchall_list_title(r.get("list_title") or "")
        and r.get("rule_type") != "content_kind"
    ]
    existing_lists = []
    seen_titles = set()
    for r in rules:
        t = (r.get("list_title") or "").strip()
        if t and t.lower() not in seen_titles:
            seen_titles.add(t.lower())
            existing_lists.append(t)
    for lst in db.fetchall(
        "SELECT title FROM lists WHERE user_id = ?", (user_id,)
    ):
        t = (lst.get("title") or "").strip()
        if (
            t
            and t.lower() not in seen_titles
            and not _is_catchall_list_title(t)
            and "скрыто" not in t.lower()
            and not _is_sync_dump_list(t)
        ):
            seen_titles.add(t.lower())
            existing_lists.append(t)
    if not existing_lists:
        return {"matched": [], "engine": "none", "reason": "Нет сохранённых категорий — сначала Разложить"}

    suggestion = llm.suggest_video_themes(
        title or "",
        channel_title or "",
        description or "",
        existing_tags=[],
        existing_lists=existing_lists,
    )
    pick = (suggestion.get("list_title") or "").strip()
    if not pick:
        return {
            "matched": [],
            "engine": suggestion.get("engine") or "llm",
            "reason": suggestion.get("reason") or "Не нашлось категории",
        }

    pick_l = pick.lower()
    chosen = None
    for r in rules:
        title_l = (r.get("list_title") or "").lower()
        if title_l == pick_l or pick_l in title_l or title_l in pick_l:
            chosen = r
            break
    if not chosen:
        for lst in db.fetchall(
            "SELECT id, title FROM lists WHERE user_id = ?", (user_id,)
        ):
            title_l = (lst.get("title") or "").lower()
            if title_l == pick_l or pick_l in title_l or title_l in pick_l:
                if _is_catchall_list_title(title_l) or "скрыто" in title_l:
                    continue
                chosen = {
                    "list_id": lst["id"],
                    "list_title": lst.get("title"),
                    "rule_type": "llm",
                    "rule_value": "",
                }
                break
    if not chosen:
        return {
            "matched": [],
            "engine": suggestion.get("engine") or "llm",
            "reason": f"LLM предложил «{pick}», но такой папки нет",
            "suggestion": pick,
        }

    _add_list_item(int(chosen["list_id"]), video_id, 0)
    _remove_from_catchall(user_id, video_id)
    return {
        "matched": [chosen],
        "engine": suggestion.get("engine") or "llm",
        "reason": suggestion.get("reason") or f"В «{chosen.get('list_title')}»",
        "suggestion": pick,
    }


def classify_pending_batch(
    user_id: int,
    *,
    limit: int = 200,
    use_llm: bool = True,
    llm_budget: int = 40,
    progress_cb=None,
) -> dict[str, Any]:
    """Sort backlog into folders. Rules/themes first; LLM for leftovers (budgeted)."""
    import time as _time

    pending = pending_to_classify(user_id, limit=limit)
    total = len(pending)
    classified = 0
    skipped = 0
    llm_used = 0
    t0 = _time.time()
    for i, item in enumerate(pending):
        vid = item["video_id"]
        # Fast path first
        result = classify_new_video(user_id, vid, use_llm=False)
        if not (result.get("matched") or []) and use_llm and llm_used < llm_budget:
            result = classify_new_video(user_id, vid, use_llm=True)
            if result.get("matched"):
                llm_used += 1
        if result.get("matched"):
            classified += 1
        else:
            skipped += 1
        if progress_cb:
            elapsed = _time.time() - t0
            pct = int(5 + 90 * (i + 1) / max(1, total))
            eta = 0.0
            if i > 0:
                eta = (elapsed / (i + 1)) * (total - i - 1)
            progress_cb(
                {
                    "pct": pct,
                    "title": "Разбираю новые",
                    "detail": f"{i + 1} из {total} · {(item.get('title') or vid)[:80]}",
                    "done": i + 1,
                    "total": total,
                    "classified": classified,
                    "elapsed_sec": elapsed,
                    "eta_sec": eta,
                }
            )
    return {
        "ok": True,
        "total": total,
        "classified": classified,
        "skipped": skipped,
        "llm_used": llm_used,
        "pending_left": len(pending_to_classify(user_id, limit=5)),
    }


def home_feed(user_id: int) -> dict[str, Any]:
    """Home spine: saved folders + recent adds + fastest-growing themes."""
    structure = saved_structure(user_id, items_per_folder=16)

    # Спецпапки YouTube (Listen later / смотреть позже) — источник правды для «Недавно»
    from backend.yt_sync import is_inbox_playlist_title

    inbox_lists = [
        r
        for r in db.fetchall(
            "SELECT id, title FROM lists WHERE user_id = ?", (user_id,)
        )
        if is_inbox_playlist_title(r.get("title") or "")
    ]
    inbox_title = ""
    recent: list[dict] = []
    if inbox_lists:
        # Prefer the largest inbox (e.g. «Тест сомтреть позже»)
        scored = []
        for lst in inbox_lists:
            c = db.fetchone(
                "SELECT COUNT(*) AS c FROM list_items WHERE list_id = ?",
                (lst["id"],),
            )
            scored.append((int((c or {}).get("c") or 0), lst))
        scored.sort(key=lambda x: -x[0])
        primary = scored[0][1]
        inbox_title = (primary.get("title") or "").replace("YT: ", "", 1).strip()
        lids = (int(primary["id"]),)
        placeholders = "?"
        if db.is_postgres():
            recent_rows = db.fetchall(
                f"""
                SELECT v.video_id, v.title, v.channel_title, v.duration_sec, v.thumb_url,
                       x.added_at AS saved_at, x.position, l.title AS list_title
                FROM list_items x
                JOIN videos v ON v.video_id = x.video_id
                JOIN lists l ON l.id = x.list_id
                LEFT JOIN library_items li
                  ON li.video_id = x.video_id AND li.user_id = ?
                WHERE x.list_id IN ({placeholders})
                  AND COALESCE(li.status, 'queue') IN ('queue', 'in_progress')
                ORDER BY x.position ASC, x.added_at DESC NULLS LAST
                LIMIT 80
                """,
                (user_id, *lids),
            )
        else:
            recent_rows = db.fetchall(
                f"""
                SELECT v.video_id, v.title, v.channel_title, v.duration_sec, v.thumb_url,
                       x.added_at AS saved_at, x.position, l.title AS list_title
                FROM list_items x
                JOIN videos v ON v.video_id = x.video_id
                JOIN lists l ON l.id = x.list_id
                LEFT JOIN library_items li
                  ON li.video_id = x.video_id AND li.user_id = ?
                WHERE x.list_id IN ({placeholders})
                  AND COALESCE(li.status, 'queue') IN ('queue', 'in_progress')
                ORDER BY x.position ASC, datetime(x.added_at) DESC
                LIMIT 80
                """,
                (user_id, *lids),
            )
    else:
        recent_rows = db.fetchall(
            """
            SELECT v.video_id, v.title, v.channel_title, v.duration_sec, v.thumb_url,
                   v.published_at, li.saved_at
            FROM library_items li
            JOIN videos v ON v.video_id = li.video_id
            WHERE li.user_id = ?
              AND li.status IN ('queue', 'in_progress')
            ORDER BY li.saved_at DESC NULLS LAST
            LIMIT 120
            """,
            (user_id,),
        ) if db.is_postgres() else db.fetchall(
            """
            SELECT v.video_id, v.title, v.channel_title, v.duration_sec, v.thumb_url,
                   v.published_at, li.saved_at
            FROM library_items li
            JOIN videos v ON v.video_id = li.video_id
            WHERE li.user_id = ?
              AND li.status IN ('queue', 'in_progress')
            ORDER BY datetime(li.saved_at) DESC
            LIMIT 120
            """,
            (user_id,),
        )

    seen_vids: set[str] = set()
    for r in recent_rows:
        if yt.is_unavailable_video(r.get("title")):
            continue
        bucket = yt.content_bucket(r.get("title"), r.get("channel_title"), r.get("duration_sec"), None)
        if bucket in ("music", "shorts", "shortform", "unavailable"):
            continue
        dur = r.get("duration_sec")
        if isinstance(dur, int) and 0 < dur <= 90:
            continue
        vid = r["video_id"]
        if vid in seen_vids:
            continue
        seen_vids.add(vid)
        recent.append(
            {
                "video_id": vid,
                "title": r.get("title") or vid,
                "channel_title": r.get("channel_title") or "",
                "duration_sec": r.get("duration_sec"),
                "duration_label": yt.format_duration(r.get("duration_sec")),
                "thumb_url": r.get("thumb_url") or yt.thumb_url(vid),
                "watch_url": f"https://www.youtube.com/watch?v={vid}",
                "saved_at": str(r.get("saved_at") or ""),
            }
        )
        if len(recent) >= 18:
            break

    if db.is_postgres():
        growing_rows = db.fetchall(
            """
            SELECT l.id, l.title, COUNT(*)::int AS added
            FROM list_items x
            JOIN lists l ON l.id = x.list_id
            WHERE l.user_id = ?
              AND x.added_at > NOW() - INTERVAL '14 days'
            GROUP BY l.id, l.title
            HAVING COUNT(*) >= 2
            ORDER BY COUNT(*) DESC
            LIMIT 10
            """,
            (user_id,),
        )
    else:
        growing_rows = db.fetchall(
            """
            SELECT l.id, l.title, COUNT(*) AS added
            FROM list_items x
            JOIN lists l ON l.id = x.list_id
            WHERE l.user_id = ?
              AND datetime(x.added_at) > datetime('now', '-14 days')
            GROUP BY l.id, l.title
            HAVING COUNT(*) >= 2
            ORDER BY COUNT(*) DESC
            LIMIT 10
            """,
            (user_id,),
        )
    growing = []
    for r in growing_rows:
        title = (r.get("title") or "").strip()
        if _is_sync_dump_list(title) or "скрыто" in title.lower():
            continue
        # Don't show inbox dump as a «growing theme» chip noise
        if is_inbox_playlist_title(title):
            continue
        growing.append(
            {
                "list_id": r["id"],
                "title": title,
                "added": int(r.get("added") or 0),
            }
        )

    pending = pending_to_classify(user_id, limit=250)
    return {
        **structure,
        "recent": recent,
        "recent_source": inbox_title or "библиотека",
        "growing": growing[:8],
        "pending_classify": len(pending),
    }
