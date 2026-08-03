# Android app (Kotlin + Jetpack Compose)

## Что есть

- **Silent share:** YouTube → Поделиться → Clip Queue → Toast «Видео сохранено!» → UI не открывается (`ShareReceiveActivity`).
- **Home:** недавно (`queue`), «могут понравиться» (`continue_vibe` / `from_playlists`), папки.
- **При входе:** `POST /api/youtube/sync` в фоне.
## Auth (Android)

1. App opens Custom Tabs → `/api/auth/google/start?client=android`
2. Google callback → `/api/auth/android/done?token=…` (HTTPS bridge)
3. Bridge opens `clipqueue://auth?token=…` / Android Intent → native app

Raw `clipqueue://` redirects from OAuth often fail inside Custom Tabs — bridge is required.
- API: `https://clip-queue-web-production.up.railway.app`

## Дизайны

Открой [`designs/index.html`](../designs/index.html) в браузере.

## Сборка

```bash
cd android-app
# Windows
.\gradlew.bat assembleDebug
```

APK: `android-app/app/build/outputs/apk/debug/app-debug.apk`

Нужны JDK 17+ и Android SDK (`local.properties` → `sdk.dir`).

## Установка

```bash
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

После первого входа через Google шаринг из YouTube начнёт сохранять ролики.

## Структура

```
android-app/app/src/main/java/ru/clipqueue/app/
  share/ShareReceiveActivity.kt   # toast-only share
  ui/screens/                     # Compose UI
  ApiClient.kt / SessionStore.kt
```
