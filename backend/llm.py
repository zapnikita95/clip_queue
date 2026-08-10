"""Cheap LLM via OpenRouter (preferred) or OpenAI-compatible base."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Optional

import requests


# Free-first chain; paid cheap fallbacks if free is rate-limited.
OR_MODEL_CHAIN = [
    "nvidia/nemotron-nano-9b-v2:free",
    "meta-llama/llama-3.2-3b-instruct:free",
    "deepseek/deepseek-chat",
    "openai/gpt-4o-mini",
]


def _config() -> tuple[Optional[str], str, list[str]]:
    """Returns (api_key, base_url, models_to_try)."""
    or_key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if or_key:
        preferred = (
            os.environ.get("OPENROUTER_MODEL") or os.environ.get("LLM_MODEL") or ""
        ).strip()
        models = []
        if preferred:
            models.append(preferred)
        for m in OR_MODEL_CHAIN:
            if m not in models:
                models.append(m)
        return or_key, "https://openrouter.ai/api/v1", models

    oa_key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if oa_key:
        base = (os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        model = (os.environ.get("OPENAI_MODEL") or "gpt-4o-mini").strip()
        return oa_key, base, [model]

    return None, "", []


def available() -> bool:
    return bool(_config()[0])


def chat_json(
    system: str,
    user: str,
    temperature: float = 0.2,
    *,
    timeout: float = 20,
    max_models: int | None = None,
) -> Optional[dict[str, Any]]:
    key, base, models = _config()
    if not key:
        return None
    if max_models is not None:
        models = models[: max(1, int(max_models))]
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    if "openrouter.ai" in base:
        headers["HTTP-Referer"] = (
            os.environ.get("PUBLIC_ORIGIN") or "https://clip-queue.local"
        )
        headers["X-Title"] = "Clip Queue"

    for model in models:
        try:
            r = requests.post(
                f"{base}/chat/completions",
                headers=headers,
                json={
                    "model": model,
                    "temperature": temperature,
                    "messages": [
                        {
                            "role": "system",
                            "content": system + " Ответь только валидным JSON без markdown.",
                        },
                        {"role": "user", "content": user},
                    ],
                },
                timeout=timeout,
            )
            if r.status_code in (404, 400):
                print(f"[llm] skip {model}: {r.status_code}", flush=True)
                continue
            if r.status_code == 429:
                print(f"[llm] rate-limit {model}, try next", flush=True)
                continue
            if r.status_code != 200:
                print(f"[llm] HTTP {r.status_code} {model}: {r.text[:200]}", flush=True)
                continue
            content = (
                (((r.json().get("choices") or [{}])[0].get("message") or {}).get("content"))
                or ""
            ).strip()
            if content.startswith("```"):
                content = content.strip("`")
                if content.lower().startswith("json"):
                    content = content[4:].strip()
            data = json.loads(content)
            data["_model"] = model
            return data
        except Exception as e:
            print(f"[llm] failed {model}: {e}", flush=True)
            continue
    return None


# Canonical short themes — safe to create during classify without title overlap.
CLASSIFY_THEME_TAGS = {
    "готовка", "музыка", "игры", "обзоры", "новости", "подкаст", "обучение",
    "история", "наука", "кино", "технологии", "спорт", "бизнес", "психология",
    "путешествия", "дизайн", "политика", "здоровье", "авто", "языки", "юмор",
    "искусство", "экономика", "программирование", "реклама", "мода",
    "документалка", "война",
}

MAX_CLASSIFY_TAGS = 3
MAX_CLASSIFY_LISTS = 3


def _tag_has_text_evidence(tag: str, title: str, channel: str, description: str) -> bool:
    """Reject slang/custom tags that have no lexical overlap with the video."""
    blob = f"{title or ''} {channel or ''} {description or ''}".lower()
    tokens = [t for t in re.split(r"[^\wа-яё]+", (tag or "").lower(), flags=re.I) if len(t) >= 3]
    if not tokens:
        return True
    return any(t in blob for t in tokens)


def _heuristic_tags(title: str, channel: str, description: str) -> list[str]:
    tags: list[str] = []
    blob = f"{title} {channel} {description}".lower()
    for word, tag in (
        ("cook", "готовка"),
        ("recipe", "готовка"),
        ("рецепт", "готовка"),
        ("готов", "готовка"),
        ("music", "музыка"),
        ("музык", "музыка"),
        ("game", "игры"),
        ("игр", "игры"),
        ("гейм", "игры"),
        ("review", "обзоры"),
        ("обзор", "обзоры"),
        ("news", "новости"),
        ("новост", "новости"),
        ("podcast", "подкаст"),
        ("подкаст", "подкаст"),
        ("tutorial", "обучение"),
        ("лекци", "обучение"),
        ("курс ", "обучение"),
        ("как ", "обучение"),
        ("истори", "история"),
        ("войн", "история"),
        ("ww2", "история"),
        ("wwii", "история"),
        ("вермахт", "история"),
        ("нацист", "история"),
        ("третий рейх", "история"),
        ("герман", "история"),
        ("документал", "документалка"),
        ("documentary", "документалка"),
        ("наук", "наука"),
        ("космос", "наука"),
        ("физик", "наука"),
        ("фильм", "кино"),
        ("сериал", "кино"),
        ("кино", "кино"),
        ("программ", "программирование"),
        ("python", "программирование"),
        ("код", "программирование"),
        ("технолог", "технологии"),
        ("гаджет", "технологии"),
        ("бизнес", "бизнес"),
        ("деньг", "бизнес"),
        ("инвест", "бизнес"),
        ("стартап", "бизнес"),
        ("спорт", "спорт"),
        ("футбол", "спорт"),
        ("психолог", "психология"),
        ("путешеств", "путешествия"),
        ("политик", "политика"),
        ("здоров", "здоровье"),
        ("авто ", "авто"),
        ("машин", "авто"),
        ("язык", "языки"),
        ("english", "языки"),
        ("юмор", "юмор"),
        ("стендап", "юмор"),
        ("дизайн", "дизайн"),
        ("искусств", "искусство"),
    ):
        if word in blob and tag not in tags:
            tags.append(tag)
    return tags[:MAX_CLASSIFY_TAGS]


def suggest_video_themes(
    title: str,
    channel: str,
    description: str,
    existing_tags: list[str],
    existing_lists: list[str],
    *,
    for_classify: bool = False,
) -> dict[str, Any]:
    """Suggest tags + list folder for one video."""
    fallback = {
        "tags": [],
        "list_title": None,
        "reason": "LLM недоступен — теги вручную",
        "engine": "none",
    }
    if for_classify:
        system = (
            "Ты классификатор YouTube-видео для личной библиотеки. "
            "Верни JSON: {\"tags\": [\"до 3 коротких тематических тегов на русском\"], "
            "\"list_titles\": [\"до 3 названий папок из existing_lists\"], "
            "\"list_title\": \"главная папка или null\", \"reason\": \"кратко почему\"}. "
            "Не больше 3 тегов и 3 папок. Теги обязательны, если тема понятна. "
            "Пример: ролик про Вторую мировую глазами немцев → tags: история, документалка, война. "
            "Предпочитай existing_tags / existing_lists. Можно короткий новый тег (1–2 слова). "
            "Не ставь личный сленг без доказательств в названии/описании."
        )
    else:
        system = (
            "Ты классификатор YouTube-видео для личного планировщика. "
            "Верни JSON: {\"tags\": [\"до 3 коротких тегов на русском\"], "
            "\"list_title\": \"название папки или null\", \"reason\": \"кратко почему\"}. "
            "Ставь тег ТОЛЬКО если он следует из названия/описания/канала. "
            "Не переиспользуй сленговые или личные теги пользователя без явных доказательств в тексте. "
            "Если уверенности нет — верни пустой tags. Не выдумывай длинные фразы — теги 1–2 слова."
        )
    data = chat_json(
        system=system,
        user=json.dumps(
            {
                "title": (title or "")[:160],
                "channel": (channel or "")[:80],
                "description": (description or "")[:400],
                "existing_tags": existing_tags[:60],
                "existing_lists": existing_lists[:40],
                "allowed_themes": sorted(CLASSIFY_THEME_TAGS) if for_classify else [],
            },
            ensure_ascii=False,
        ),
    )
    if not data:
        tags = _heuristic_tags(title, channel, description)
        return {
            "tags": tags,
            "list_title": tags[0] if tags else None,
            "list_titles": tags[:MAX_CLASSIFY_LISTS] if tags else [],
            "reason": "Эвристика по словам (без LLM)",
            "engine": "heuristic",
        }
    tags = []
    for t in data.get("tags") or []:
        name = str(t).strip()[:40]
        if name and name not in tags:
            tags.append(name)
    # Prefer existing tag names; gate slang; allow canonical themes on classify
    lower_map = {x.lower(): x for x in existing_tags}
    remapped = []
    for t in tags:
        canon = lower_map.get(t.lower(), t)
        is_existing = canon.lower() in lower_map
        is_theme = canon.lower() in CLASSIFY_THEME_TAGS
        has_ev = _tag_has_text_evidence(canon, title, channel, description)
        if is_existing and not has_ev and not is_theme:
            continue
        if not is_existing and not has_ev and not (for_classify and is_theme):
            continue
        # Reject long slang phrases even on classify
        if len(canon.split()) >= 3 and not has_ev:
            continue
        remapped.append(canon)
    if for_classify and not remapped:
        remapped = _heuristic_tags(title, channel, description)
    tags = remapped[:MAX_CLASSIFY_TAGS]
    list_title = data.get("list_title")
    list_titles: list[str] = []
    for lt in data.get("list_titles") or ([] if not list_title else [list_title]):
        name = str(lt).strip()[:80]
        if not name:
            continue
        for el in existing_lists:
            if el.lower() == name.lower():
                name = el
                break
        if name not in list_titles:
            list_titles.append(name)
        if len(list_titles) >= MAX_CLASSIFY_LISTS:
            break
    if list_title:
        list_title = str(list_title).strip()[:80] or None
        for el in existing_lists:
            if el.lower() == list_title.lower():
                list_title = el
                break
        if list_title and list_title not in list_titles:
            list_titles = [list_title] + [x for x in list_titles if x != list_title]
            list_titles = list_titles[:MAX_CLASSIFY_LISTS]
    elif list_titles:
        list_title = list_titles[0]
    return {
        "tags": tags,
        "list_title": list_title,
        "list_titles": list_titles,
        "reason": str(data.get("reason") or "")[:240],
        "engine": "llm",
    }
