"""Similar videos — only inside the user's library.

Ranking prefers multi-signal content match (title + description + tags +
personal note) over a single shared buzzword. Same-channel is a bonus but
results are diversified so the rail is not only «ещё от этого автора».
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from typing import Any

_TOKEN_RE = re.compile(r"[a-zA-Zа-яА-ЯёЁ0-9]{3,}", re.UNICODE)

# Ultra-common tokens that alone should not decide «похоже»
_STOP = {
    "это", "как", "что", "для", "или", "все", "всё", "the", "and", "for", "with",
    "you", "your", "how", "what", "why", "not", "from", "this", "that", "видео",
    "ролик", "канал", "новый", "новые", "часть", "серия", "выпуск", "полный",
    "смотри", "смотреть", "today", "episode", "part", "season",
}


def tokens(text: str) -> set[str]:
    return _tokens(text)


def _tokens(text: str) -> set[str]:
    out = set()
    for t in _TOKEN_RE.findall(text or ""):
        tl = t.lower()
        if tl in _STOP or len(tl) < 3:
            continue
        out.add(tl)
    return out


def _token_list(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "") if t.lower() not in _STOP and len(t) >= 3]


def parse_tags_json(raw: str | None) -> list[str]:
    try:
        v = json.loads(raw or "[]")
        return list(v) if isinstance(v) else []
    except Exception:
        return []


def _content_blob(item: dict) -> str:
    parts = [
        item.get("title") or "",
        (item.get("description") or "")[:900],
        " ".join(item.get("tags") or []),
        item.get("note") or "",
        item.get("channel_title") or "",
    ]
    return " ".join(parts)


def _idf_weights(docs_tokens: list[set[str]]) -> dict[str, float]:
    n = max(1, len(docs_tokens))
    df: Counter[str] = Counter()
    for toks in docs_tokens:
        df.update(toks)
    return {t: math.log(1 + n / (1 + c)) for t, c in df.items()}


def score(
    a: dict,
    b: dict,
    shared_user_tags: int = 0,
    *,
    idf: dict[str, float] | None = None,
) -> float:
    if a.get("video_id") == b.get("video_id"):
        return -1.0

    idf = idf or {}
    s = 0.0

    # Channel: useful but not dominant
    same_ch = False
    if a.get("channel_id") and a.get("channel_id") == b.get("channel_id"):
        s += 2.2
        same_ch = True
    elif a.get("channel_title") and a.get("channel_title") == b.get("channel_title"):
        s += 1.6
        same_ch = True

    ta = {_t.lower() for _t in (a.get("tags") or []) if _t}
    tb = {_t.lower() for _t in (b.get("tags") or []) if _t}
    if ta and tb:
        s += min(2.4, 0.55 * len(ta & tb))

    title_a = _tokens(a.get("title") or "")
    title_b = _tokens(b.get("title") or "")
    title_ov = title_a & title_b
    if title_ov:
        w = sum(idf.get(t, 1.0) for t in title_ov)
        s += min(3.0, 0.55 * w)

    desc_a = _tokens((a.get("description") or "")[:900])
    desc_b = _tokens((b.get("description") or "")[:900])
    desc_ov = desc_a & desc_b
    if desc_ov:
        w = sum(idf.get(t, 1.0) for t in desc_ov)
        # Description overlap is the main «really similar» signal
        s += min(4.5, 0.35 * w)

    # Title↔description cross (show/topic mentioned in the other)
    cross = (title_a & desc_b) | (title_b & desc_a)
    if cross:
        w = sum(idf.get(t, 1.0) for t in cross)
        s += min(2.5, 0.4 * w)

    note_a = _tokens(a.get("note") or "")
    note_b = _tokens(b.get("note") or "")
    if note_a and note_b:
        nov = note_a & note_b
        if nov:
            s += min(3.5, 0.9 * len(nov))
    # Personal note of either side matching the other's content
    if note_a:
        s += min(2.0, 0.45 * len(note_a & (title_b | desc_b)))
    if note_b:
        s += min(2.0, 0.45 * len(note_b & (title_a | desc_a)))

    da, db_ = a.get("duration_sec"), b.get("duration_sec")
    if isinstance(da, int) and isinstance(db_, int) and da > 0 and db_ > 0:
        ratio = min(da, db_) / max(da, db_)
        if ratio >= 0.7:
            s += 0.6
        elif ratio >= 0.5:
            s += 0.3

    if shared_user_tags:
        s += min(2.5, 0.85 * shared_user_tags)

    # Penalize weak single-token title-only matches (e.g. only «война»)
    content_hits = len(title_ov) + len(desc_ov) + len(cross)
    if content_hits <= 1 and not same_ch and not shared_user_tags and not (ta & tb):
        s *= 0.35
    elif content_hits >= 4:
        s += 1.2  # boost multi-signal likeness toward the front

    return s


def diversify(ranked: list[tuple[float, dict]], limit: int, *, max_per_channel: int = 3) -> list[dict[str, Any]]:
    """Keep score order but cap same-channel domination."""
    out: list[dict[str, Any]] = []
    ch_count: Counter[str] = Counter()
    deferred: list[tuple[float, dict]] = []

    def ch_key(item: dict) -> str:
        return (item.get("channel_id") or item.get("channel_title") or "").strip().lower()

    for sc, c in ranked:
        key = ch_key(c)
        if key and ch_count[key] >= max_per_channel:
            deferred.append((sc, c))
            continue
        item = dict(c)
        item["similarity"] = round(sc, 2)
        out.append(item)
        if key:
            ch_count[key] += 1
        if len(out) >= limit:
            return out

    for sc, c in deferred:
        if len(out) >= limit:
            break
        item = dict(c)
        item["similarity"] = round(sc, 2)
        out.append(item)
    return out


def rank_similar(
    anchor: dict,
    candidates: list[dict],
    tag_overlap: dict[str, int] | None = None,
    limit: int = 12,
) -> list[dict[str, Any]]:
    tag_overlap = tag_overlap or {}
    docs = [_tokens(_content_blob(anchor))] + [_tokens(_content_blob(c)) for c in candidates]
    idf = _idf_weights(docs)

    scored: list[tuple[float, dict]] = []
    for c in candidates:
        sc = score(
            anchor,
            c,
            shared_user_tags=tag_overlap.get(c["video_id"], 0),
            idf=idf,
        )
        if sc >= 0.8:  # drop noise
            scored.append((sc, c))
    scored.sort(key=lambda x: -x[0])
    return diversify(scored, limit, max_per_channel=3)


def related_search_query(title: str, channel_title: str = "", description: str = "") -> str:
    """Build a YouTube search query that captures the topic, not only the channel."""
    title = (title or "").strip()
    # Drop episode noise
    cleaned = re.sub(r"[\[\(].*?[\]\)]", " ", title)
    cleaned = re.sub(r"\b(часть|часть\s*\d+|part\s*\d+|ep\.?\s*\d+|выпуск\s*\d+)\b", " ", cleaned, flags=re.I)
    toks = [t for t in _token_list(cleaned) if t not in _STOP][:6]
    if len(toks) < 2:
        toks = _token_list(title)[:5]
    # Pull distinctive words from description start
    for t in _token_list((description or "")[:280]):
        if t not in toks and t not in _STOP:
            toks.append(t)
        if len(toks) >= 7:
            break
    q = " ".join(toks[:7])
    if not q and channel_title:
        q = channel_title
    return q.strip() or title[:80]
