# Google OAuth setup

## Прод сейчас

Clip Queue использует **тот же** OAuth client, что Movie Planner:

- Railway `movie_planner` / `api-web` → `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET`
- скопированы в `clip_queue` / `clip-queue-web` как `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` (и алиасы `GOOGLE_OAUTH_*`)

Новый client в Google Cloud создавать **не нужно**.

## Один ручной шаг (обязательно)

В Google Cloud Console того же проекта, что Movie Planner:

1. [APIs & Services → Credentials](https://console.cloud.google.com/apis/credentials)
2. Открой OAuth 2.0 Client ID (Web) — тот, что у Movie Planner (`436134608618-…`)
3. **Authorized redirect URIs** → Add URI:

```
https://clip-queue-web-production.up.railway.app/api/auth/google/callback
```

4. Save

Без этого Google ответит `redirect_uri_mismatch`.

## YouTube Data API

В том же GCP-проекте включи (если ещё нет):

- **YouTube Data API v3**

На OAuth consent screen добавь scope (Sensitive):

- `https://www.googleapis.com/auth/youtube.readonly`

Пока app в Testing — твой Google-аккаунт должен быть в **Test users**.

## Local (опционально)

Добавь ещё redirect:

```
http://127.0.0.1:8765/api/auth/google/callback
```