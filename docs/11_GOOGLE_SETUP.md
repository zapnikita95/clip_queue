# Google OAuth setup

1. [Google Cloud Console](https://console.cloud.google.com/) → новый проект `clip-queue`
2. APIs & Services → Enable **YouTube Data API v3**
3. OAuth consent screen → External → scopes:
   - `openid`, `email`, `profile`
   - `https://www.googleapis.com/auth/youtube.readonly`
4. Credentials → Create OAuth client ID → **Web application**
5. Authorized redirect URIs:
   - `https://clip-queue-web-production.up.railway.app/api/auth/google/callback`
   - `http://127.0.0.1:8765/api/auth/google/callback` (local)
6. Railway variables на `clip-queue-web`:
   - `GOOGLE_CLIENT_ID`
   - `GOOGLE_CLIENT_SECRET`
   - `PUBLIC_ORIGIN=https://clip-queue-web-production.up.railway.app`
7. Пока app в Testing — добавь свой Google-аккаунт в Test users.

Пока credentials не заданы, кнопка Google на логине скрыта (остаётся dev-вход).