# Kyro FCM setup

Пуши после классификации требуют Firebase.

## 1. Android client

1. Создай проект Firebase (или используй существующий).
2. Add Android app: package `ru.clipqueue.app`.
3. Скачай **настоящий** `google-services.json` → замени  
   `android-app/app/google-services.json` (в репо лежит stub для сборки).
4. Пересобери APK.

## 2. Backend (Railway)

1. Firebase Console → Project settings → Service accounts → Generate new private key.
2. В Railway env:

```
FIREBASE_SERVICE_ACCOUNT_JSON={"type":"service_account",...весь JSON одной строкой...}
```

Либо файл + `FIREBASE_SERVICE_ACCOUNT_PATH=/path/to/sa.json` (локально).

3. Redeploy. Без этой переменной classify в фоне работает, пуш логируется как `fcm_unconfigured`.

## 3. Проверка

1. Войти в Kyro → разрешить уведомления.
2. `POST /api/devices/register` должен пройти (лог `device registered` в logcat).
3. Share из YouTube → toast «Сохранено в Kyro» за секунды.
4. Через несколько секунд/десятков — пуш `«…» → Папка` → тап → карточка видео.
