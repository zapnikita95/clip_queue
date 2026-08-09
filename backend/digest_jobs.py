"""Weekly digest auto-send worker (in-process, enabled on web)."""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Optional

from backend import db, now_plan, push

log = logging.getLogger("clip_queue.digest")

_started = False
_lock = threading.Lock()


def _env_bool(name: str, default: bool = True) -> bool:
    raw = (os.environ.get(name) or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def in_quiet_hours(prefs: dict, *, now: Optional[datetime] = None) -> bool:
    """Quiet hours local to UTC hour if no tz — prefs: quiet_start/quiet_end 0-23."""
    qs = prefs.get("quiet_start")
    qe = prefs.get("quiet_end")
    if qs is None or qe is None:
        return False
    try:
        qs_i, qe_i = int(qs), int(qe)
    except (TypeError, ValueError):
        return False
    hour = (now or datetime.now(timezone.utc)).hour
    if qs_i == qe_i:
        return False
    if qs_i < qe_i:
        return qs_i <= hour < qe_i
    # wraps midnight
    return hour >= qs_i or hour < qe_i


def should_send_weekly(prefs: dict, *, now: Optional[datetime] = None) -> bool:
    if prefs.get("digest_enabled") is False:
        return False
    if in_quiet_hours(prefs, now=now):
        return False
    now = now or datetime.now(timezone.utc)
    # Default: Sunday 10:00–11:00 UTC (tunable via digest_weekday / digest_hour)
    weekday = int(prefs.get("digest_weekday", 6))  # 0=Mon … 6=Sun
    hour = int(prefs.get("digest_hour", 10))
    if now.weekday() != weekday or now.hour != hour:
        return False
    last = (prefs.get("digest_last_sent") or "").strip()
    if last:
        try:
            last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
            if (now - last_dt).total_seconds() < 5 * 24 * 3600:
                return False
        except Exception:
            pass
    return True


def send_digest_for_user(user_id: int) -> dict:
    prefs = now_plan.get_prefs(user_id)
    if prefs.get("digest_enabled") is False:
        return {"ok": True, "sent": 0, "skipped": "disabled"}
    dig = now_plan.weekly_digest(user_id)
    result = push.send_to_user(
        user_id,
        title=dig["title"],
        body=dig["body"],
        data={"type": "digest", "route": "/"},
    )
    now_plan.set_prefs(
        user_id,
        {"digest_last_sent": datetime.now(timezone.utc).isoformat()},
    )
    return {"ok": True, "sent": int((result or {}).get("sent") or 0), "push": result}


def tick() -> dict:
    """Scan users with prefs and send due digests + due reminders."""
    from backend import reminders_svc

    users = db.fetchall("SELECT id FROM users LIMIT 5000")
    dig_sent = 0
    rem_sent = 0
    now = datetime.now(timezone.utc)
    for u in users:
        uid = int(u["id"])
        prefs = now_plan.get_prefs(uid)
        if should_send_weekly(prefs, now=now):
            try:
                r = send_digest_for_user(uid)
                dig_sent += int(r.get("sent") or 0)
            except Exception as e:
                log.warning("digest user=%s: %s", uid, e)
        if in_quiet_hours(prefs, now=now):
            continue
        try:
            due = reminders_svc.due_reminders(uid)
            for item in due[:5]:
                push.send_to_user(
                    uid,
                    title="Напоминание Kyro",
                    body=(item.get("title") or "Ролик ждёт вас")[:120],
                    data={
                        "type": "reminder",
                        "video_id": item["video_id"],
                        "route": f"/v/{item['video_id']}",
                    },
                )
                reminders_svc.complete_reminder(uid, int(item["id"]))
                rem_sent += 1
        except Exception as e:
            log.warning("reminder user=%s: %s", uid, e)
    return {"ok": True, "digest_pushes": dig_sent, "reminder_pushes": rem_sent}


def start_background(*, interval_sec: int = 900) -> None:
    """Daemon thread: every interval_sec run tick. Disable with DIGEST_CRON=0."""
    global _started
    if not _env_bool("DIGEST_CRON", True):
        log.info("digest cron disabled (DIGEST_CRON=0)")
        return
    with _lock:
        if _started:
            return
        _started = True

    def loop():
        # delay first tick so gunicorn binds
        time.sleep(45)
        while True:
            try:
                stats = tick()
                log.info("digest tick %s", stats)
            except Exception as e:
                log.warning("digest tick failed: %s", e)
            time.sleep(max(120, interval_sec))

    t = threading.Thread(target=loop, name="kyro-digest-cron", daemon=True)
    t.start()
    log.info("digest cron started interval=%ss", interval_sec)
