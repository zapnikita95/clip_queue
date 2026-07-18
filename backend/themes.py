"""Thematic buckets for organize / classify (RU labels, keyword + channel hints)."""

from __future__ import annotations

import re
from typing import Any

# Each theme: title shown to user, keywords (title/channel), optional channel substrings.
# First matching theme wins when scoring (higher score = better).
THEMES: list[dict[str, Any]] = [
    {
        "id": "english",
        "title": "Про английский",
        "keywords": [
            r"\benglish\b",
            r"\benglishbad\b",
            r"английск",
            r"\bie\s*lts\b",
            r"\btoefl\b",
            r"\bphrasal\b",
            r"\bvocabulary\b",
            r"\bgrammar\b",
            r"произношени",
            r"\bpronunciation\b",
            r"\bbee\s*fluent\b",
            r"english\s+class",
            r"учить\s+англий",
        ],
        "channels": [
            "englishbad",
            "english class",
            "engvid",
            "bbc learning english",
            "rachel's english",
            "english with lucy",
        ],
    },
    {
        "id": "languages",
        "title": "Про языки",
        "keywords": [
            r"\blanguage\b",
            r"языки?",
            r"иностранн",
            r"\bpolyglot\b",
            r"\bspanish\b",
            r"\bfrench\b",
            r"\bgerman\b",
            r"\bchinese\b",
            r"\bjapanese\b",
            r"испанск",
            r"французск",
            r"немецк",
            r"китайск",
            r"японск",
            r"полиглот",
            r"изучени[ея]\s+язык",
        ],
        "channels": ["easy languages", "language"],
    },
    {
        "id": "news",
        "title": "Новости",
        "keywords": [
            r"\bnews\b",
            r"новост",
            r"редакци",
            r"выпуск\s+новост",
            r"\bнеделя\b",
            r"сводка",
            r"политик",
            r"войн[аеуы]",
            r"санкци",
            r"выборы",
        ],
        "channels": [
            "редакция",
            "дождь",
            "bbc news",
            "dw на русском",
            "current time",
            "настоящее время",
            "руслан усачев",
            "вдудь",
        ],
    },
    {
        "id": "history",
        "title": "История",
        "keywords": [
            r"истори",
            r"\bhistory\b",
            r"древн",
            r"средневек",
            r"ссср",
            r"\bwii\b",
            r"втор(ая|ой)\s+миров",
            r"революци",
            r"импери",
            r"архив",
            r"документальн.*истори",
        ],
        "channels": [
            "история",
            "history",
            "егор язов",
            "миньон истории",
            "simple history",
        ],
    },
    {
        "id": "science",
        "title": "Наука",
        "keywords": [
            r"наук",
            r"\bscience\b",
            r"физик",
            r"хими",
            r"биолог",
            r"космос",
            r"\bspace\b",
            r"астрон",
            r"эволюци",
            r"нейро",
            r"квант",
        ],
        "channels": ["veritasium", "vsauce", "kurzgesagt", "постнаука", "наука"],
    },
    {
        "id": "tech",
        "title": "Технологии",
        "keywords": [
            r"технолог",
            r"\btech\b",
            r"\bai\b",
            r"искусственн.*интеллект",
            r"нейросет",
            r"программ",
            r"\bcoding\b",
            r"\bpython\b",
            r"гаджет",
            r"смартфон",
            r"apple",
            r"google",
            r"стартап",
        ],
        "channels": [
            "wylsacom",
            "rozetked",
            "the verge",
            "marques brownlee",
            "михаил климов",
        ],
    },
    {
        "id": "cinema",
        "title": "Кино и сериалы",
        "keywords": [
            r"кино",
            r"фильм",
            r"сериал",
            r"режиссёр",
            r"режиссер",
            r"\bmovie\b",
            r"\bfilm\b",
            r"\bcinema\b",
            r"кинопоиск",
            r"обзор.*фильм",
            r"трейлер",
        ],
        "channels": ["кинопоиск", "badcomedian", "кино", "letterboxd"],
    },
    {
        "id": "travel",
        "title": "Путешествия",
        "keywords": [
            r"путешеств",
            r"\btravel\b",
            r"поездк",
            r"город[аеу]",
            r"страна",
            r"туризм",
            r"отель",
            r"аэропорт",
            r"влог.*город",
        ],
        "channels": ["travel", "путешеств", "indygogo"],
    },
    {
        "id": "food",
        "title": "Еда и готовка",
        "keywords": [
            r"готовк",
            r"рецепт",
            r"кухн",
            r"\bcook\b",
            r"\brecipe\b",
            r"еда",
            r"ресторан",
            r"кафе",
        ],
        "channels": ["bon appétit", "tasty", "готовка"],
    },
    {
        "id": "psychology",
        "title": "Психология",
        "keywords": [
            r"психолог",
            r"ментальн",
            r"тревог",
            r"депресс",
            r"самооценк",
            r"отношени",
            r"\btherapy\b",
            r"мотивац",
        ],
        "channels": ["психолог"],
    },
    {
        "id": "business",
        "title": "Бизнес и деньги",
        "keywords": [
            r"бизнес",
            r"инвестиц",
            r"деньг",
            r"финанс",
            r"стартап",
            r"предпринимат",
            r"\bstartup\b",
            r"акци",
            r"крипт",
        ],
        "channels": ["бизнес"],
    },
    {
        "id": "comedy",
        "title": "Юмор",
        "keywords": [
            r"юмор",
            r"стендап",
            r"\bstandup\b",
            r"комик",
            r"прикол",
            r"смешн",
            r"\bcomedy\b",
        ],
        "channels": ["кшиштовск", "standup", "labelcom", "чбд"],
    },
    {
        "id": "documentary",
        "title": "Документалка",
        "keywords": [
            r"документал",
            r"\bdocumentary\b",
            r"расследован",
            r"репортаж",
            r"спецпроект",
        ],
        "channels": [],
    },
    {
        "id": "sports",
        "title": "Спорт",
        "keywords": [
            r"спорт",
            r"футбол",
            r"хоккей",
            r"теннис",
            r"\bnba\b",
            r"тренировк",
            r"фитнес",
        ],
        "channels": [],
    },
    {
        "id": "games",
        "title": "Игры",
        "keywords": [
            r"\bgameplay\b",
            r"\bgaming\b",
            r"игра[хю]?",
            r"прохожден",
            r"\bsteam\b",
            r"киберспорт",
        ],
        "channels": [],
    },
]


def _compile_theme(theme: dict[str, Any]) -> dict[str, Any]:
    return {
        **theme,
        "_kw": [re.compile(p, re.I) for p in theme.get("keywords") or []],
        "_ch": [c.lower() for c in (theme.get("channels") or [])],
    }


_COMPILED = [_compile_theme(t) for t in THEMES]
_BY_ID = {t["id"]: t for t in _COMPILED}


def theme_by_id(theme_id: str) -> dict[str, Any] | None:
    return _BY_ID.get(theme_id)


def score_theme(theme: dict[str, Any], title: str, channel: str) -> int:
    blob = f"{title or ''} {channel or ''}"
    ch_l = (channel or "").lower()
    score = 0
    for ch in theme.get("_ch") or []:
        if ch and ch in ch_l:
            score += 5
    for rx in theme.get("_kw") or []:
        if rx.search(blob):
            score += 2
    # English theme should not steal pure "languages" unless english-specific
    if theme["id"] == "languages" and score_theme(_BY_ID["english"], title, channel) >= 4:
        score = max(0, score - 3)
    return score


def detect_themes(title: str | None, channel_title: str | None, *, min_score: int = 2) -> list[dict[str, Any]]:
    """Return themes sorted by score desc (may be empty)."""
    title = title or ""
    channel = channel_title or ""
    scored = []
    for theme in _COMPILED:
        sc = score_theme(theme, title, channel)
        if sc >= min_score:
            scored.append((sc, theme))
    scored.sort(key=lambda x: (-x[0], x[1]["title"]))
    return [t for _, t in scored]


def primary_theme(title: str | None, channel_title: str | None) -> dict[str, Any] | None:
    themes = detect_themes(title, channel_title, min_score=2)
    return themes[0] if themes else None


def matches_theme(theme_id: str, title: str | None, channel_title: str | None) -> bool:
    theme = theme_by_id(theme_id)
    if not theme:
        return False
    return score_theme(theme, title or "", channel_title or "") >= 2
