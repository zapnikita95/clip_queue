# Умный поиск, похожие, личная лексика

## Что сделано

1. **Похожие из твоих** — ранжирование по title + description + YT tags + личная заметка, IDF (редкие слова важнее), диверсификация каналов. Слабое совпадение в одно слово («война») уходит вниз.
2. **Похожие на YouTube** — `search.list` по теме ролика (`relatedToVideoId` у Google закрыт). Кнопка «В очередь».
3. **Умная строка** в шапке + страница `/search`. BM25 по библиотеке (~1k ок без vector DB). LLM (если ключ) разбирает «не стендап / геймплей не обзор». Голос: Web Speech API; fallback Whisper если есть `OPENAI_API_KEY`.
4. **Личная лексика** — поле «Как ты это назовёшь» на странице ролика; попап после «Просмотрено». Заметки участвуют в поиске и similar.

## Почему не сразу embeddings

На 800–1000 роликов на пользователя BM25 на лету дешевле и проще, чем отдельный индекс/pgvector на каждого. Vectors — фаза 2, если BM25+заметки не хватит.

## История просмотров YouTube

Data API **не отдаёт** watch history. Takeout / ручная разметка / заметка после watched — рабочие пути.

## Синтетика лексики

```bash
cd clip_queue
python -m scripts.seed_lexicon_notes --user-email YOU@mail.com --dry-run
python -m scripts.seed_lexicon_notes --user-email YOU@mail.com --apply
```
