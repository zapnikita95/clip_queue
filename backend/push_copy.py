"""Human-readable FCM copy: headline ≠ video title."""

from __future__ import annotations

import random
from typing import Optional

MORNING_HEADLINES = (
    "Рекомендуем посмотреть",
    "Вам может быть интересно",
    "Идея на сегодня",
)


def _clip(text: str, limit: int) -> str:
    s = (text or "").strip()
    if not s:
        return ""
    if len(s) <= limit:
        return s
    return s[: max(1, limit - 1)] + "…"


def video_label(title: str, *, fallback: str = "Ролик из вашей очереди") -> str:
    return _clip(title or fallback, 200)


def morning(video_title: str, *, reason: str = "") -> tuple[str, str]:
    headline = random.choice(MORNING_HEADLINES)
    body = video_label(video_title)
    why = (reason or "").strip()
    if why:
        body = f"{body}\n{why}"
    return headline, _clip(body, 400)


def reminder(video_title: str) -> tuple[str, str]:
    return "Напоминание", _clip(video_label(video_title), 400)


def classified(video_title: str, folder_titles: list[str]) -> tuple[str, str]:
    body = video_label(video_title, fallback="Видео")
    folders = [f.strip() for f in folder_titles if (f or "").strip()]
    if folders:
        body = f"{body}\n→ {', '.join(folders[:3])}"
    else:
        body = f"{body}\nСохранено в очередь"
    return "Сохранено в Kyro", _clip(body, 400)
