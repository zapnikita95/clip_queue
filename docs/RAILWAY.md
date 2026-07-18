# Railway — отдельный сервис

Clip Queue **не** деплоится в проект Movie Planner.

## Один раз

1. [railway.app](https://railway.app) → **New Project**
2. **Deploy from GitHub** → `zapnikita95/clip_queue`
3. **Add PostgreSQL** в этот же новый проект (свой инстанс)
4. Variables на web-сервисе:

| Var | Value |
|-----|--------|
| `SECRET_KEY` | длинная случайная строка |
| `DATABASE_URL` | из Postgres (Reference) |
| `DEV_LOGIN` | `0` |
| `YOUTUBE_API_KEY` | опционально |
| `PUBLIC_ORIGIN` | `https://<railway-domain>` |

5. Generate Domain → проверить `GET /health` → `{"service":"clip_queue",...}`

## Не делать

- Не добавлять этот репо в Railway-проект movie_planner_bot
- Не шарить `DATABASE_URL` с Movie Planner
- Не ставить `DEV_LOGIN=1` на проде