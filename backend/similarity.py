"""Similar videos — only inside the user's library."""

from __future__ import annotations

import json
import re
from typing import Any

_TOKEN_RE = re.compile(r"[a-zA-Zа-яА-ЯёЁ0-9]{3,}", re.UNICODE)


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in _TOKEN_RE.findall(text or "")}


def score(a: dict, b: dict, shared_user_tags: int = 0) -> float:
    if a.get("video_id") == b.get("video_id"):
        return -1.0
    s = 0.0
    if a.get("channel_id") and a.get("channel_id") == b.get("channel_id"):
        s += 3.0
    elif a.get("channel_title") and a.get("channel_title") == b.get("channel_title"):
        s += 2.0

    ta = set(a.get("tags") or [])
    tb = set(b.get("tags") or [])
    if ta and tb:
        s += min(2.0, 0.4 * len(ta & tb))

    title_overlap = _tokens(a.get("title") or "") & _tokens(b.get("title") or "")
    s += min(1.5, 0.25 * len(title_overlap))

    da, db_ = a.get("duration_sec"), b.get("duration_sec")
    if isinstance(da, int) and isinstance(db_, int) and da > 0 and db_ > 0:
        ratio = min(da, db_) / max(da, db_)
        if ratio >= 0.7:
            s += 0.8
        elif ratio >= 0.5:
            s += 0.4

    if shared_user_tags:
        s += min(2.0, 0.7 * shared_user_tags)

    return s


def rank_similar(
    anchor: dict,
    candidates: list[dict],
    tag_overlap: dict[str, int] | None = None,
    limit: int = 12,
) -> list[dict[str, Any]]:
    tag_overlap = tag_overlap or {}
    scored: list[tuple[float, dict]] = []
    for c in candidates:
        sc = score(anchor, c, shared_user_tags=tag_overlap.get(c["video_id"], 0))
        if sc > 0:
            scored.append((sc, c))
    scored.sort(key=lambda x: -x[0])
    out = []
    for sc, c in scored[:limit]:
        item = dict(c)
        item["similarity"] = round(sc, 2)
        out.append(item)
    return out


def parse_tags_json(raw: str | None) -> list[str]:
    try:
        v = json.loads(raw or "[]")
        return list(v) if isinstance(v, list) else []
    except Exception:
        return []
