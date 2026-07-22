"""In-library smart search: BM25 + optional LLM constraint parse.

For ~1k videos per user a full vector DB is overkill — BM25 over
title+description+tags+personal note is fast and per-request.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Optional

from backend import llm

_TOKEN_RE = re.compile(r"[a-zA-Zа-яА-ЯёЁ0-9]{3,}", re.UNICODE)
_STOP = {
    "это", "как", "что", "для", "или", "все", "всё", "the", "and", "for", "with",
    "you", "видео", "ролик", "какой", "нибудь", "хочу", "посмотреть", "найти",
}


def tokenize(text: str) -> list[str]:
    out = []
    for t in _TOKEN_RE.findall(text or ""):
        tl = t.lower()
        if tl in _STOP or len(tl) < 3:
            continue
        out.append(tl)
    return out


def _doc_text(item: dict) -> str:
    return " ".join(
        [
            item.get("title") or "",
            (item.get("description") or "")[:1200],
            " ".join(item.get("tags") or []),
            item.get("note") or "",
            item.get("channel_title") or "",
            " ".join(
                f"{(t.get('emoji') or '')} {(t.get('name') or '')}"
                for t in (item.get("user_tags") or [])
                if isinstance(t, dict)
            ),
        ]
    )


def bm25_rank(
    query: str,
    items: list[dict],
    *,
    limit: int = 40,
    k1: float = 1.5,
    b: float = 0.75,
) -> list[dict[str, Any]]:
    q_toks = tokenize(query)
    if not q_toks or not items:
        return []

    docs = [tokenize(_doc_text(it)) for it in items]
    N = len(docs)
    avgdl = sum(len(d) for d in docs) / max(1, N)
    df: Counter[str] = Counter()
    for d in docs:
        df.update(set(d))

    def idf(t: str) -> float:
        n_q = df.get(t, 0)
        return math.log(1 + (N - n_q + 0.5) / (n_q + 0.5))

    scored: list[tuple[float, dict]] = []
    for it, doc in zip(items, docs):
        if not doc:
            continue
        tf = Counter(doc)
        dl = len(doc)
        score = 0.0
        # Personal note hits get a boost (user lexicon)
        note_toks = set(tokenize(it.get("note") or ""))
        for t in q_toks:
            if t not in tf:
                continue
            freq = tf[t]
            denom = freq + k1 * (1 - b + b * dl / max(avgdl, 1))
            score += idf(t) * (freq * (k1 + 1)) / denom
            if t in note_toks:
                score += 1.8
        if score > 0:
            scored.append((score, it))

    scored.sort(key=lambda x: -x[0])
    out = []
    for sc, it in scored[:limit]:
        row = dict(it)
        row["search_score"] = round(sc, 3)
        out.append(row)
    return out


def parse_query_constraints(query: str) -> dict[str, Any]:
    """Use LLM when available; else cheap RU heuristics for negations."""
    q = (query or "").strip()
    fallback = {
        "rewritten": q,
        "must": [],
        "must_not": [],
        "prefer": [],
    }
    # Heuristic: «не X», «без X»
    for m in re.finditer(r"(?:не|без)\s+([a-zA-Zа-яА-ЯёЁ0-9\-]{3,})", q, re.I):
        fallback["must_not"].append(m.group(1).lower())
    if "стендап" in q.lower() or "standup" in q.lower():
        if any(x in q.lower() for x in ("не ", "без ", "кроме")):
            fallback["must_not"].append("стендап")
            fallback["must_not"].append("standup")
    if "геймплей" in q.lower() and "обзор" in q.lower() and "не" in q.lower():
        fallback["prefer"].append("геймплей")
        fallback["must_not"].append("обзор")

    if not llm.available() or len(q) < 4:
        return fallback

    data = llm.chat_json(
        "Ты разбираешь поисковый запрос по личной библиотеке YouTube. "
        "Верни JSON: rewritten (короткий поисковый запрос), must (слова которые должны быть), "
        "must_not (чего избегать), prefer (желательно). Язык — как у пользователя.",
        f"Запрос: {q}",
        temperature=0.1,
        timeout=12,
        max_models=2,
    )
    if not isinstance(data, dict):
        return fallback
    return {
        "rewritten": (data.get("rewritten") or q).strip() or q,
        "must": [str(x).lower() for x in (data.get("must") or []) if x][:8],
        "must_not": [str(x).lower() for x in (data.get("must_not") or []) if x][:8],
        "prefer": [str(x).lower() for x in (data.get("prefer") or []) if x][:8],
        "_model": data.get("_model"),
    }


def apply_constraints(items: list[dict], constraints: dict[str, Any]) -> list[dict]:
    must_not = [t.lower() for t in (constraints.get("must_not") or [])]
    must = [t.lower() for t in (constraints.get("must") or [])]
    prefer = [t.lower() for t in (constraints.get("prefer") or [])]
    if not must_not and not must and not prefer:
        return items

    filtered = []
    for it in items:
        blob = _doc_text(it).lower()
        if must_not and any(n in blob for n in must_not):
            continue
        if must and not all(m in blob for m in must):
            # soft: keep but demote later via score — skip hard filter if too strict
            if len(must) == 1 and must[0] not in blob:
                continue
        if prefer:
            hits = sum(1 for p in prefer if p in blob)
            it = dict(it)
            it["search_score"] = float(it.get("search_score") or 0) + 0.6 * hits
        filtered.append(it)
    filtered.sort(key=lambda x: -float(x.get("search_score") or 0))
    return filtered


def smart_search(query: str, items: list[dict], *, limit: int = 36) -> dict[str, Any]:
    constraints = parse_query_constraints(query)
    q2 = constraints.get("rewritten") or query
    ranked = bm25_rank(q2, items, limit=limit * 2)
    ranked = apply_constraints(ranked, constraints)
    return {
        "query": query,
        "interpreted": constraints,
        "items": ranked[:limit],
    }
