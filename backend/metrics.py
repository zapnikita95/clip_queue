"""Surface / planned-watch metrics for Kyro north star."""

from __future__ import annotations

from typing import Any, Optional

from backend import db

# Taxonomy (event_type values stored in surface_events + subset in watch_events)
SURFACE_TYPES = frozenset(
    {
        "now_impression",  # saw «Сейчас» picks
        "now_open",  # opened a pick from «Сейчас»
        "plan_open",  # opened from tonight/week plan
        "digest_open",  # opened from digest push / preview
        "suggestion_open",  # opened a smart suggestion
        "push_open",  # opened from classify push
        "planned_watch",  # opened YouTube from a plan surface (north-star unit)
    }
)


def ensure_tables() -> None:
    if db.is_postgres():
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS surface_events (
              id SERIAL PRIMARY KEY,
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              video_id TEXT NOT NULL DEFAULT '',
              event_type TEXT NOT NULL,
              surface TEXT NOT NULL DEFAULT '',
              meta_json TEXT NOT NULL DEFAULT '{}',
              at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_surface_events_user_at ON surface_events(user_id, at DESC)"
        )
    else:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS surface_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
              video_id TEXT NOT NULL DEFAULT '',
              event_type TEXT NOT NULL,
              surface TEXT NOT NULL DEFAULT '',
              meta_json TEXT NOT NULL DEFAULT '{}',
              at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_surface_events_user_at ON surface_events(user_id, at DESC)"
        )


def track(
    user_id: int,
    event_type: str,
    *,
    video_id: str = "",
    surface: str = "",
    meta: Optional[dict] = None,
) -> dict[str, Any]:
    import json

    ensure_tables()
    et = (event_type or "").strip()
    if et not in SURFACE_TYPES:
        return {"ok": False, "error": "unknown_event"}
    db.execute(
        """
        INSERT INTO surface_events (user_id, video_id, event_type, surface, meta_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            user_id,
            (video_id or "")[:40],
            et,
            (surface or "")[:80],
            json.dumps(meta or {}, ensure_ascii=False),
        ),
    )
    # Mirror north-star opens into watch_events for continuity
    if et in ("planned_watch", "now_open", "plan_open", "suggestion_open", "digest_open"):
        try:
            db.execute(
                "INSERT INTO watch_events (user_id, video_id, event_type) VALUES (?, ?, ?)",
                (user_id, (video_id or "unknown")[:40], et),
            )
        except Exception:
            pass
    return {"ok": True, "event_type": et}


def weekly_summary(user_id: int) -> dict[str, Any]:
    """North star + habit rough counters for last 7 days."""
    ensure_tables()
    if db.is_postgres():
        rows = db.fetchall(
            """
            SELECT event_type, COUNT(*) AS c
            FROM surface_events
            WHERE user_id = ? AND at >= NOW() - INTERVAL '7 days'
            GROUP BY event_type
            """,
            (user_id,),
        )
        planned = db.fetchone(
            """
            SELECT COUNT(*) AS c FROM surface_events
            WHERE user_id = ? AND event_type = 'planned_watch'
              AND at >= NOW() - INTERVAL '7 days'
            """,
            (user_id,),
        )
        surface_days = db.fetchone(
            """
            SELECT COUNT(DISTINCT DATE(at AT TIME ZONE 'UTC')) AS c
            FROM surface_events
            WHERE user_id = ?
              AND event_type IN ('now_open','plan_open','suggestion_open','digest_open','push_open','planned_watch')
              AND at >= NOW() - INTERVAL '7 days'
            """,
            (user_id,),
        )
    else:
        rows = db.fetchall(
            """
            SELECT event_type, COUNT(*) AS c
            FROM surface_events
            WHERE user_id = ? AND at >= datetime('now', '-7 days')
            GROUP BY event_type
            """,
            (user_id,),
        )
        planned = db.fetchone(
            """
            SELECT COUNT(*) AS c FROM surface_events
            WHERE user_id = ? AND event_type = 'planned_watch'
              AND at >= datetime('now', '-7 days')
            """,
            (user_id,),
        )
        surface_days = db.fetchone(
            """
            SELECT COUNT(DISTINCT date(at)) AS c
            FROM surface_events
            WHERE user_id = ?
              AND event_type IN ('now_open','plan_open','suggestion_open','digest_open','push_open','planned_watch')
              AND at >= datetime('now', '-7 days')
            """,
            (user_id,),
        )

    by_type = {r["event_type"]: int(r["c"] or 0) for r in rows}
    # Depth: % of queue in thematic lists
    queue_n = db.fetchone(
        "SELECT COUNT(*) AS c FROM library_items WHERE user_id = ? AND status IN ('queue','in_progress')",
        (user_id,),
    )
    in_theme = db.fetchone(
        """
        SELECT COUNT(DISTINCT li.video_id) AS c
        FROM library_items li
        JOIN list_items lsi ON lsi.video_id = li.video_id
        JOIN lists l ON l.id = lsi.list_id AND l.user_id = li.user_id
        WHERE li.user_id = ? AND li.status IN ('queue', 'in_progress')
          AND l.title NOT LIKE ?
          AND lower(l.title) NOT LIKE ?
        """,
        (user_id, "YT:%", "%скрыто%"),
    )
    q = int((queue_n or {}).get("c") or 0)
    t = int((in_theme or {}).get("c") or 0)
    depth_pct = round(100.0 * t / q, 1) if q else 0.0
    return {
        "weekly_planned_watches": int((planned or {}).get("c") or 0),
        "surface_active_days": int((surface_days or {}).get("c") or 0),
        "by_type": by_type,
        "depth_themed_pct": depth_pct,
        "queue_count": q,
        "themed_count": t,
        "north_star": "weekly_planned_watches",
    }
