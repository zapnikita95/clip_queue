"""Thematic buckets for organize / classify (RU labels, keyword + channel hints)."""

from __future__ import annotations

import re
from typing import Any

# Order matters for display defaults; scoring decides assignment.
# Prefer specific themes (driving) over vague ones (travel via «город»).
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
        ],
        "channels": [],
    },
    {
        "id": "driving",
        "title": "Вождение и ПДД",
        "keywords": [
            r"вождени",
            r"на\s+вождени",
            r"автошкол",
            r"\bпдд\b",
            r"экзамен.*вод",
            r"сдача.*вод",
            r"сдам\s+на\s+права",
            r"акпп",
            r"мкпп",
            r"механик[аеуи]",
            r"передач[уиае]",
            r"перед\s+поворотом",
            r"поворот",
            r"парковк",
            r"права\b",
            r"водительск",
            r"автодром",
            r"гибдд",
            r"грубая ошибк",
            r"инструктор",
            r"уроки?\s+вожд",
            r"езд[аыуе].*город",
            r"город.*езд",
            r"за\s+рул[еёя]",
            r"рул[еёя]",
            # EN — titles often English even for RU driving schools
            r"\bdriving\b",
            r"\bdriver'?s?\s+license\b",
            r"\bdriving\s+exam\b",
            r"\bgear\b",
            r"\bshift(ing)?\b",
            r"\bclutch\b",
            r"\bmanual\s+transmission\b",
            r"\bautomatic\s+transmission\b",
            r"\bparking\b",
            r"\binstructor\b",
            r"behind\s+the\s+wheel",
        ],
        "channels": [
            "автошкола",
            "автошкола red",
            "novokshonov",
            "новокшонов",
            "пдд",
            "автоинструктор",
        ],
        "negatives": [],
        "weight": 3,  # stronger than generic themes
    },
    {
        "id": "news",
        "title": "Новости",
        "keywords": [
            r"новост",
            r"\bnews\b",
            r"сегодня",
            r"сводка",
            r"политик",
            r"выборы",
        ],
        "channels": ["редакция", "вдудь", "дождь", "bbc", "cnn"],
    },
    {
        "id": "history",
        "title": "История",
        "keywords": [
            r"истори",
            r"средневек",
            r"древн",
            r"импери",
            r"войн[аыуе]",
            r"\bhistory\b",
            r"археолог",
        ],
        "channels": ["arzamas", "история", "кликклак", "по чёрному", "по черному"],
        "negatives": [r"зашкварн.*истори"],  # clickbait «stories» not history
    },
    {
        "id": "science",
        "title": "Наука",
        "keywords": [
            r"наук",
            r"физик",
            r"хими",
            r"биологи",
            r"космос",
            r"\bscience\b",
            r"эксперимент",
        ],
        "channels": ["veritasium", "vsauce", "наука"],
    },
    {
        "id": "tech",
        "title": "Технологии",
        "keywords": [
            r"технолог",
            r"гаджет",
            r"смартфон",
            r"\bihone\b",
            r"iphone",
            r"android",
            r"нейросет",
            r"\bai\b",
            r"chatgpt",
            r"обзор.*(телефон|ноутбук|наушник)",
        ],
        "channels": [
            "the verge",
            "marques brownlee",
            "михаил климов",
            "wylsacom",
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
            r"\bобзор\b",
            r"\breview\b",
            r"трейлер",
            r"\bmarvel\b",
            r"\bthor\b",
            r"тор\s*\d",
            r"кинокритик",
            r"премьер",
        ],
        "channels": ["кинопоиск", "badcomedian", "кино", "letterboxd"],
        "weight": 3,
    },
    {
        "id": "travel",
        "title": "Путешествия",
        "keywords": [
            r"путешестви[еяй]",
            r"\btravel\b",
            r"туризм",
            r"отель",
            r"аэропорт",
            r"влог.*(город|стран|отпуск)",
            r"отпуск",
            r"backpack",
            r"куда\s+поехать",
        ],
        "channels": ["travel", "indygogo", "поехавший"],
        # «путешествие в отмену», вождение «в городе» — не travel
        "negatives": [
            r"отмен[уеа]",
            r"cancel",
            r"cancellation",
            r"\bjourney\s+into\b",  # metaphor, not tourism
            r"вождени",
            r"автошкол",
            r"экзамен",
            r"пдд",
            r"передач",
            r"акпп",
            r"инструктор",
            r"права\b",
        ],
    },
    {
        "id": "food",
        "title": "Еда и готовка",
        "keywords": [
            r"готовк",
            r"рецепт",
            r"кухн[яи]",
            r"\bcook\b",
            r"\brecipe\b",
            r"ресторан",
            r"шеф.?повар",
            r"ивл[её]в",
            r"бургер",
            r"десерт",
        ],
        "channels": ["bon appétit", "tasty", "готовка", "ивл"],
        "negatives": [
            r"передач",
            r"акпп",
            r"вождени",
            r"автошкол",
            r"поворот",
            r"механик",
        ],
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
            r"\bfunny\b",
            r"\bcomedy\b",
            r"угарн",
        ],
        "channels": ["кшиштовск", "standup", "labelcom", "чбд"],
        "weight": 3,
        "negatives": [
            r"обзор.*(фильм|кино|сериал|тор)",
            r"\bthor\b",
            r"\breview\b",
            r"кинопоиск",
            r"автошкол",
            r"экзамен.*вод",
            r"\bпдд\b",
            r"передач[уиае]",
            r"\bgear\b",
            r"\bshift(ing)?\b",
        ],
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
        ],
        "channels": [],
    },
    {
        "id": "games",
        "title": "Игры",
        "keywords": [
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
        "_neg": [re.compile(p, re.I) for p in theme.get("negatives") or []],
    }


_COMPILED = [_compile_theme(t) for t in THEMES]
_BY_ID = {t["id"]: t for t in _COMPILED}


def theme_by_id(theme_id: str) -> dict[str, Any] | None:
    return _BY_ID.get(theme_id)


def score_theme(theme: dict[str, Any], title: str, channel: str, description: str = "") -> int:
    blob = f"{title or ''} {channel or ''} {(description or '')[:400]}"
    ch_l = (channel or "").lower()
    score = 0
    for neg in theme.get("_neg") or []:
        if neg.search(blob):
            return 0
    kw_w = int(theme.get("weight") or 2)
    for ch in theme.get("_ch") or []:
        if ch and ch in ch_l:
            score += 6
    for rx in theme.get("_kw") or []:
        if rx.search(blob):
            score += kw_w
    # English theme should not steal pure "languages" unless english-specific
    if theme["id"] == "languages" and score_theme(_BY_ID["english"], title, channel, description) >= 4:
        score = max(0, score - 3)
    # Cinema beats comedy when both fire on film reviews
    if theme["id"] == "comedy":
        cine = score_theme(_BY_ID["cinema"], title, channel, description)
        if cine >= 4:
            score = max(0, score - 4)
    # Driving must beat travel/food on exam/city-driving titles
    if theme["id"] in ("travel", "food"):
        drive = score_theme(_BY_ID["driving"], title, channel, description)
        if drive >= 3:
            score = 0
    # Instructional driving ≠ comedy; funny-while-driving can stay multi-theme
    if theme["id"] == "comedy":
        drive = score_theme(_BY_ID["driving"], title, channel, description)
        if drive >= 3:
            funny = bool(
                re.search(r"смешн|прикол|funny|угар|compilation\s+of\s+funny", blob, re.I)
            )
            if not funny:
                score = 0
    return score


def detect_themes(
    title: str | None,
    channel_title: str | None,
    *,
    description: str | None = None,
    min_score: int = 3,
) -> list[dict[str, Any]]:
    """Return themes sorted by score desc (may be empty)."""
    title = title or ""
    channel = channel_title or ""
    desc = description or ""
    scored = []
    for theme in _COMPILED:
        sc = score_theme(theme, title, channel, desc)
        if sc >= min_score:
            scored.append((sc, theme))
    scored.sort(key=lambda x: (-x[0], x[1]["title"]))
    return [t for _, t in scored]


def primary_theme(
    title: str | None,
    channel_title: str | None,
    *,
    description: str | None = None,
) -> dict[str, Any] | None:
    themes = detect_themes(title, channel_title, description=description, min_score=3)
    return themes[0] if themes else None


def matches_theme(
    theme_id: str,
    title: str | None,
    channel_title: str | None,
    *,
    description: str | None = None,
) -> bool:
    theme = theme_by_id(theme_id)
    if not theme:
        return False
    return score_theme(theme, title or "", channel_title or "", description or "") >= 3
