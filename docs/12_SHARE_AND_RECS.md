# Share → auto-categorize → push (Kyro north star)

## Как пользователь кладёт видео

1. В YouTube находит ролик → **Поделиться → Kyro**.
2. Android `ShareReceiveActivity` дергает `POST /api/videos/save` с
   `classify_async: true` (короткий timeout — только resolve + upsert).
3. Сразу toast **«Сохранено в Kyro»** и `finish()` — YouTube не блокируется.
4. Бэкенд в фоне (`share_classify`):
   - применяет classify_rules / themes / LLM в существующие папки;
   - пишет `save_events`;
   - шлёт FCM: title `Kyro`, body `«{title}» → {папка}` (без `llm` / engine в UI).
5. Тап по пушу → `clipqueue://video/{video_id}` → карточка видео в приложении.

Музыку/короткие клипы по-прежнему не кладём в план (archive), см. `content_bucket`.

## API

| Поле save | Поведение |
|-----------|-----------|
| `classify_async: true` | Классификация в фоне + пуш |
| `source: android_share` / `share_target` / `pwa_share` | Async по умолчанию |
| sync (paste из приложения без флага) | Как раньше — classify в HTTP |

Устройства: `POST /api/devices/register` `{ token, platform }`.

FCM: см. [FIREBASE_PUSH.md](FIREBASE_PUSH.md).

## Почему не весь «Смотреть позже»

YouTube Data API **не отдаёт** системный плейлист `WL`.  
Синк = лайки + обычные плейлисты. Обход: пользовательский плейлист-копия или share по одному.

## Рекомендации «лучше чем YouTube»

- тот же `theme` rule / канал / пересечение тегов;
- rail `continue_vibe` уже ранжирует по каналу/тегам/длине;
- не предлагать music/shortform/unavailable;
- «похожие с других каналов про историю» = theme match + diversify channel.

Ресурсы: heuristic + дешёвый LLM только на share без матча (в фоне).

## Прокси-просмотр YouTube (не реализовано)

Платный in-app просмотр через наш прокси — отдельный контур (~4–8 недель): yt-dlp/Invidious-like + Media3 + отдельный egress (не Railway) + billing + ToS-риски.  
Доминирует трафик (порядок 1–3 ГБ/час на зрителя), не CPU Flask. Сейчас не строим — см. `docs/13_PROXY_WATCH_EVAL.md`.
