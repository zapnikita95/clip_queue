# Метрики Kyro

## North star

**Weekly Planned Watches** — число событий `planned_watch` за 7 дней: пользователь открыл ролик на YouTube из поверхности плана Kyro (`Сейчас`, план вечер/неделя, подсказка, дайджест, пуш, напоминание).

## Surface events (`surface_events`)

| event_type | Когда |
|------------|--------|
| `now_impression` | Показали блок «Сейчас» |
| `now_open` | Клик/open из «Сейчас» |
| `plan_open` | Из плана tonight/week |
| `suggestion_open` | Из умной подсказки |
| `digest_open` | Из дайджеста |
| `push_open` | Из classify-пуша |
| `planned_watch` | Open YT с surface плана (north star unit) |

API: `POST /api/metrics/track`, `GET /api/metrics/summary`.

## Activation / Habit / Depth / Trust (сводка в `/api/metrics/summary`)

- **Habit proxy:** `surface_active_days` — дни с surface-open за неделю.
- **Depth:** `depth_themed_pct` — доля очереди в тематических папках (не YT:).
- **Trust:** classify «Не туда» → `classify_rules` (качественная петля; CTR пуш — в FCM отдельно).
- **Activation:** share/sync + ≥1 папка — смотреть `save_events` + `lists` (продуктовый чеклист онбординга).
