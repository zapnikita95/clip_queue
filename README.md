# Clip Queue

Сестринский сервис к [Movie Planner](https://movie-planner.ru): очередь YouTube-видео из **твоих** интересов.

- Отдельный репозиторий, отдельная БД, отдельный Railway
- Никакой общей базы с Movie Planner
- Веб-кабинет: сохранить по ссылке → главная с рельсами → теги и списки → похожие из своих
- **Android (Kotlin + Compose):** share из YouTube → Toast «Видео сохранено!» без открытия UI; home + sync плейлистов — см. [`android-app/`](android-app/) и [`docs/14_ANDROID_APP.md`](docs/14_ANDROID_APP.md). Мокапы: [`designs/index.html`](designs/index.html)

## Локально

```bash
cd clip_queue
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m backend.app
```

Открой [http://127.0.0.1:8765](http://127.0.0.1:8765) → **Быстрый вход (dev)**.

## Railway (отдельный сервис)

1. New Project → Deploy from GitHub → этот репо
2. Add Plugin → **PostgreSQL** (свой инстанс, не Movie Planner)
3. Variables:
   - `SECRET_KEY` — случайная строка
   - `DATABASE_URL` — из Postgres plugin (Railway подставит)
   - `DEV_LOGIN=0` на проде
   - `YOUTUBE_API_KEY` — опционально (без ключа работает oEmbed)
   - `PUBLIC_ORIGIN=https://<your-domain>`
4. Healthcheck: `/health`

`Dockerfile` + `railway.json` уже в репо.

## Продукт (MVP)

| Раздел | Что делает |
|--------|------------|
| Главная | Рельсы: очередь, недавно, вайб, длительность, каналы, «в это время» |
| Очередь | Watch Later |
| Добавить | Paste URL / `?url=` / PWA share_target |
| Списки + теги | Свои подборки |
| Карточка `/v/{id}` | Превью, открыть на YT, похожие из библиотеки |

## Стек

Python 3.12 · Flask · Gunicorn · SQLite (local) / Postgres (Railway) · static SPA в `web/`

## Документация

См. [`docs/`](docs/).