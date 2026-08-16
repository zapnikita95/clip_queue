"""User purpose packs (study / work / entertainment) → active theme taxonomy."""

from __future__ import annotations

from typing import Any

from backend import themes

PURPOSE_IDS = ("study", "work", "entertainment")
DEFAULT_PURPOSES = ["entertainment"]

PURPOSE_LABELS = {
    "study": "Учёба",
    "work": "Работа",
    "entertainment": "Развлечение",
}

# Broad topic folders (existing THEMES ids).
ENTERTAINMENT_THEME_IDS = [
    "news",
    "history",
    "science",
    "tech",
    "cinema",
    "travel",
    "food",
    "psychology",
    "business",
    "comedy",
    "documentary",
    "sports",
    "games",
    "driving",
]

WORK_THEME_IDS = [
    "business",
    "tech",
    "work_productivity",
    "work_career",
    "work_tools",
    "work_presentations",
]

STUDY_THEME_IDS = [
    "study_english",
    "study_languages",
    "study_math",
    "study_programming",
    "study_exams",
    "study_lectures",
    "study_science",
    "study_history",
    "study_psychology",
    "study_notes",
]

PURPOSE_PACKS: dict[str, list[str]] = {
    "entertainment": ENTERTAINMENT_THEME_IDS,
    "work": WORK_THEME_IDS,
    "study": STUDY_THEME_IDS,
}

def normalize_purposes(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return list(DEFAULT_PURPOSES)
    out: list[str] = []
    seen: set[str] = set()
    for x in raw:
        pid = str(x or "").strip().lower()
        if pid in PURPOSE_IDS and pid not in seen:
            seen.add(pid)
            out.append(pid)
    return out or list(DEFAULT_PURPOSES)


def purpose_catalog() -> list[dict[str, str]]:
    return [{"id": k, "label": PURPOSE_LABELS[k]} for k in PURPOSE_IDS]


def daypart_defaults_for_purposes(purposes: list[str]) -> dict[str, list[str]]:
    """Suggested morning/evening daypart theme ids for first purpose save."""
    morning: list[str] = []
    evening: list[str] = []
    if "study" in purposes:
        morning.extend(["обучение", "подкаст"])
    if "work" in purposes:
        morning.extend(["бизнес", "технологии"])
    if "entertainment" in purposes:
        morning.extend(["новости"])
        evening.extend(["кино", "документалка", "юмор"])
    if "study" in purposes and "история" not in evening:
        evening.extend(["история", "наука"])
    if "work" in purposes and not evening:
        evening.extend(["технологии", "бизнес"])
    # de-dupe preserve order
    def uniq(xs: list[str]) -> list[str]:
        s: set[str] = set()
        o: list[str] = []
        for x in xs:
            if x not in s:
                s.add(x)
                o.append(x)
        return o[:6]

    if not morning:
        morning = ["новости", "обучение", "подкаст"]
    if not evening:
        evening = ["история", "документалка", "кино"]
    return {"morning_themes": uniq(morning), "evening_themes": uniq(evening)}


def theme_ids_for_purposes(purposes: list[str]) -> list[str]:
    purposes = normalize_purposes(purposes)
    ordered: list[str] = []
    seen: set[str] = set()
    # Prefer study specificity first, then work, then entertainment
    for pack in ("study", "work", "entertainment"):
        if pack not in purposes:
            continue
        for tid in PURPOSE_PACKS.get(pack) or []:
            if tid not in seen:
                seen.add(tid)
                ordered.append(tid)
    return ordered


def active_themes_for_purposes(purposes: list[str] | None = None) -> list[dict[str, Any]]:
    ids = theme_ids_for_purposes(purposes or DEFAULT_PURPOSES)
    out: list[dict[str, Any]] = []
    for tid in ids:
        th = themes.theme_by_id(tid)
        if th:
            out.append(th)
    return out


def get_user_purposes(user_id: int) -> list[str]:
    from backend import now_plan

    prefs = now_plan.get_prefs(user_id)
    return normalize_purposes(prefs.get("use_purposes"))


def active_themes_for_user(user_id: int) -> list[dict[str, Any]]:
    return active_themes_for_purposes(get_user_purposes(user_id))
