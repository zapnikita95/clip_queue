# Kyro FCM setup

Пуши после классификации идут через Firebase project **movie-planner-7fcad** (тот же, что Movie Planner).

## Android

- Package: `ru.clipqueue.app`
- Файл: `android-app/app/google-services.json` (реальный, не stub)
- App id: `1:275185236379:android:efcdd84fcc6a158d43493e`

## Backend (Railway)

Env на `clip-queue-web`:

```
FIREBASE_SERVICE_ACCOUNT_JSON=<JSON firebase-adminsdk service account>
```

Код читает его в `backend/push.py`. Без переменной classify в фоне работает, пуш = no-op.

Локально для отладки можно положить JSON в `data/firebase-admin-kyro.json` и:

```
FIREBASE_SERVICE_ACCOUNT_PATH=data/firebase-admin-kyro.json
```

(`/data/` в `.gitignore` — секреты не коммитить.)

## Проверка

1. Установить APK ≥ 0.1.15, войти, разрешить уведомления.
2. Logcat: `KyroPush` → `device registered`.
3. Share из YouTube → toast «Сохранено в Kyro».
4. Пуш `«…» → Папка` → тап → карточка видео.
