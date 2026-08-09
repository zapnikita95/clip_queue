# Kyro iOS 1.0

Expo app: **Сейчас**, папки, сохранение URL, deep link `kyro://`.

## Запуск

```bash
cd ios-app
npm start
# i — симулятор / устройство через Expo Go
# или: npx expo run:ios   # native build / TestFlight prep
```

API: `extra.apiBaseUrl` в `app.json` → Railway prod.

## Share

1. Из YouTube Share → «Скопировать» → вкладка **Сохранить** в Kyro.
2. Deep link: `kyro://save?url=https://youtu.be/...`
3. Нативный Share Extension (Xcode): после `npx expo prebuild` добавьте Share Extension target, который открывает `kyro://save?url=...`. Исходник-скелет: `ShareExtension/ShareViewController.swift`.

## Auth

Google OAuth с `client=ios&redirect=kyro://auth`, либо вставка `cq_session_token` из веба.
