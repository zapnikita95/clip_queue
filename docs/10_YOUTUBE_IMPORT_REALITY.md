# YouTube import — что реально можно

## Жёсткий факт (Google, не мы)

Через **YouTube Data API v3 + OAuth** **нельзя** получить:

| Данные | Статус API |
|--------|------------|
| Watch Later (`WL`) | закрыто (`watchLaterNotAccessible`) |
| История просмотров (`HL`) | закрыто (`watchHistoryNotAccessible`) |
| «Досмотреть» / progress % | **нет endpoint’а вообще** |

Даже с полными scopes `youtube.readonly` / `youtube` — WL и history отдают пусто/403.

## Что можно забрать OAuth’ом (база продукта)

| Источник | Как |
|----------|-----|
| Профиль Google + email | OpenID |
| Лайкнутые (`LL`) | `channels.mine` → `relatedPlaylists.likes` → `playlistItems` |
| Свои плейлисты | `playlists.list?mine=true` + items |
| Подписки | `subscriptions.list?mine=true` |
| Метаданные видео | `videos.list` / oEmbed |

Это уже даёт «что человеку важно» — не полная история, но живой вкус и планы в плейлистах.

## Как закрыть дыру «не досмотрел / watch later»

| Путь | UX | Надёжность |
|------|-----|------------|
| **A. Google Takeout** (watch-history JSON) | «Скачай Takeout → загрузи файл» | Официально, коряво, но легально |
| **B. Browser extension** (читает WL в сессии YT) | Один клик, как Share | Хрупко, серая зона ToS |
| **C. Ручной share/paste** | Уже есть | Всегда работает |

**MVP сейчас:** A + OAuth sync (лайки/плейлисты) + LLM-раскладка.  
**«Не досмотрел до конца»:** в Takeout нет процента просмотра; приближение — «смотрел / вернулся / в истории, но не в лайках» + пользовательский статус `in_progress`. Настоящий Continue Watching — только через extension (фаза 2).

## Онбординг

1. Войти через Google (обязательный путь).
2. Синк лайков + плейлистов + подписок.
3. Опционально: загрузить Takeout history.
4. LLM предлагает структуру папок (темы / каналы / длина / «похоже на планы»).
5. Пользователь принимает / правит → создаём `lists` + теги.