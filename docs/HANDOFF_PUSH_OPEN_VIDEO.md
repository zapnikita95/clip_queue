# Handoff: клик в пуш не открывал видео

**Дата:** 2026-08-11  
**Репо:** `clip_queue` (Kyro) · коммит `b9a17f1` · backend `0.4.2` · Android `0.1.21`

## Симптом

Тап по FCM-уведомлению не открывает карточку видео.

## Корень

В `backend/push.py` стояло `click_action="OPEN_VIDEO"`, а в Manifest у MainActivity не было intent-filter → система не находила activity.

## Фикс (уже в main)

1. `click_action=OPEN_MAIN` + filters в Manifest  
2. data: `video_id`, `deeplink`, `route`  
3. MainActivity читает FCM extras  

## На домашнем ПК

```bash
cd ~/Desktop/Кино/clip_queue && git pull
cd android-app
export ANDROID_HOME="$HOME/Library/Android/sdk"
./gradlew :app:assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

Проверка: утренний пуш / share classify → тап → экран видео.

Рядом в релизе: поиск на главной, кликабельный «сегодня».
