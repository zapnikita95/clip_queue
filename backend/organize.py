"""Propose folder structure for user's library (LLM or heuristic)."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from typing import Any

from backend import db, llm

_TOKEN = re.compile(r"[a-zA-Zа-яА-ЯёЁ0-9]{3,}", re.UNICODE)


def _library_snapshot(user_id: int, limit: int = 400) -> list[dict]:
    rows = db.fetchall(
        """
        SELECT v.video_id, v.title, v.channel_title, v.duration_sec, li.status, li.source
        FROM library_items li
        JOIN videos v ON v.video_id = li.video_id
        WHERE li.user_id = ?
        ORDER BY li.saved_at DESC
        LIMIT ?
        """,
        (user_id, limit),
    )
    return rows


def heuristic_propose(user_id: int) -> dict[str, Any]:
    rows = _library_snapshot(user_id)
    by_channel: dict[str, list[str]] = defaultdict(list)
    by_status: dict[str, list[str]] = defaultdict(list)
    short: list[str] = []
    long_: list[str] = []
    tokens: Counter = Counter()

    for r in rows:
        ch = (r.get("channel_title") or "Без канала").strip() or "Без канала"
        by_channel[ch].append(r["video_id"])
        by_status[r.get("status") or "queue"].append(r["video_id"])
        dur = r.get("duration_sec")
        if isinstance(dur, int):
            if dur < 600:
                short.append(r["video_id"])
            elif dur >= 2400:
                long_.append(r["video_id"])
        for t in _TOKEN.findall(r.get("title") or ""):
            tokens[t.lower()] += 1

    folders = []
    queue = by_status.get("queue") or []
    watched = by_status.get("watched") or []
    if queue:
        folders.append(
            {
                "title": "В очереди / не разобрано",
                "reason": "Всё, что ещё не отмечено просмотренным",
                "video_ids": queue[:80],
            }
        )
    if short:
        folders.append(
            {
                "title": "Короткие (<10 мин)",
                "reason": "Удобно добить вечером или в дороге",
                "video_ids": short[:60],
            }
        )
    if long_:
        folders.append(
            {
                "title": "Длинные (40+ мин)",
                "reason": "Нужен слот времени",
                "video_ids": long_[:60],
            }
        )

    # top channels as folders
    top_ch = sorted(by_channel.items(), key=lambda x: -len(x[1]))[:8]
    for ch, vids in top_ch:
        if len(vids) < 2:
            continue
        folders.append(
            {
                "title": f"Канал: {ch}"[:80],
                "reason": f"{len(vids)} видео с этого канала в твоей базе",
                "video_ids": vids[:40],
            }
        )

    # keyword buckets from titles
    for word, cnt in tokens.most_common(12):
        if cnt < 3 or word in {"the", "and", "для", "как", "это", "что", "you", "with"}:
            continue
        vids = [
            r["video_id"]
            for r in rows
            if word in (r.get("title") or "").lower()
        ][:40]
        if len(vids) >= 3:
            folders.append(
                {
                    "title": f"Тема: {word}",
                    "reason": f"Часто встречается в названиях ({cnt})",
                    "video_ids": vids,
                }
            )
        if len(folders) >= 16:
            break

    if watched:
        folders.append(
            {
                "title": "Уже смотрел (история)",
                "reason": "Из Takeout / отмеченных — чтобы не путать с очередью",
                "video_ids": watched[:80],
            }
        )

    return {
        "engine": "heuristic",
        "summary": (
            f"В библиотеке {len(rows)} видео. "
            f"В очереди {len(queue)}, в истории/просмотренных {len(watched)}. "
            "Watch Later и «не досмотрел %» Google API не отдаёт — "
            "ниже раскладка по каналам, длине и словам из названий."
        ),
        "folders": folders[:16],
        "limitations": [
            "Нет официального доступа к Watch Later и Continue Watching",
            "Для истории нужен Google Takeout",
        ],
    }


def llm_propose(user_id: int) -> dict[str, Any] | None:
    if not llm.available():
        return None
    rows = _library_snapshot(user_id, limit=80)
    if len(rows) < 3:
        return None
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
    # Free OpenRouter models often queue 60–180s — hard cap so UX never hangs.
    data = llm.chat_json(
        system=(
            "Ты помогаешь разобрать личную библиотеку YouTube-видео. "
            "Ответ JSON: {\"summary\": string, \"folders\": [{\"title\", \"reason\", \"video_ids\": []}]}. "
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
        folders.append(
            {
                "title": str(f.get("title") or "Папка")[:120],
                "reason": str(f.get("reason") or "")[:300],
                "video_ids": vids[:50],
            }
        )
    if not folders:
        return None
    return {
        "engine": "llm",
        "summary": str(data.get("summary") or "")[:800],
        "folders": folders[:16],
        "limitations": [
            "Нет официального доступа к Watch Later и Continue Watching",
        ],
    }


def propose_structure(user_id: int, *, use_llm: bool = False) -> dict[str, Any]:
    """Default = instant heuristic. LLM only if use_llm=1 (and still ≤10s)."""
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


def apply_proposal(user_id: int, proposal: dict) -> dict[str, Any]:
    created = []
    for folder in proposal.get("folders") or []:
        title = (folder.get("title") or "").strip()[:120]
        vids = folder.get("video_ids") or []
        if not title or not vids:
            continue
        existing = db.fetchone(
            "SELECT id FROM lists WHERE user_id = ? AND title = ?",
            (user_id, title),
        )
        if existing:
            list_id = int(existing["id"])
        elif db.is_postgres():
            with db.connect() as conn:
                cur = conn.execute(
                    "INSERT INTO lists (user_id, title) VALUES (%s, %s) RETURNING id",
                    (user_id, title),
                )
                list_id = int(cur.fetchone()["id"])
        else:
            db.execute("INSERT INTO lists (user_id, title) VALUES (?, ?)", (user_id, title))
            list_id = int(
                db.fetchone(
                    "SELECT id FROM lists WHERE user_id = ? AND title = ?",
                    (user_id, title),
                )["id"]
            )
        n = 0
        for vid in vids:
            db.execute(
                "INSERT INTO list_items (list_id, video_id, position) VALUES (?, ?, ?) "
                + (
                    "ON CONFLICT DO NOTHING"
                    if db.is_postgres()
                    else "ON CONFLICT(list_id, video_id) DO NOTHING"
                ),
                (list_id, vid, n),
            )
            n += 1
        created.append({"id": list_id, "title": title, "count": n})
    return {"ok": True, "lists": created}
