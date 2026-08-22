"""Weekly digest + daily morning push worker (in-process on web)."""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone
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


def _local_now(prefs: dict, *, now: Optional[datetime] = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    try:
        offset = int(prefs.get("tz_offset_hours", 3))
    except (TypeError, ValueError):
        offset = 3
    return now.astimezone(timezone.utc) + timedelta(hours=offset)


def in_quiet_hours(prefs: dict, *, now: Optional[datetime] = None) -> bool:
    """Quiet hours in user local time (tz_offset_hours)."""
    qs = prefs.get("quiet_start")
    qe = prefs.get("quiet_end")
    if qs is None or qe is None:
        return False
    try:
        qs_i, qe_i = int(qs), int(qe)
    except (TypeError, ValueError):
        return False
    hour = _local_now(prefs, now=now).hour
    if qs_i == qe_i:
        return False
    if qs_i < qe_i:
        return qs_i <= hour < qe_i
    return hour >= qs_i or hour < qe_i


def should_send_weekly(prefs: dict, *, now: Optional[datetime] = None) -> bool:
    if prefs.get("digest_enabled") is False:
        return False
    if in_quiet_hours(prefs, now=now):
        return False
    local = _local_now(prefs, now=now)
    weekday = int(prefs.get("digest_weekday", 6))  # 0=Mon … 6=Sun
    hour = int(prefs.get("digest_hour", 10))
    if local.weekday() != weekday or local.hour != hour:
        return False
    last = (prefs.get("digest_last_sent") or "").strip()
    if last:
        try:
            last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
            if (datetime.now(timezone.utc) - last_dt).total_seconds() < 5 * 24 * 3600:
                return False
        except Exception:
            pass
    return True


def should_send_morning(prefs: dict, *, now: Optional[datetime] = None) -> bool:
    if prefs.get("morning_push_enabled") is False:
        return False
    if in_quiet_hours(prefs, now=now):
        return False
    local = _local_now(prefs, now=now)
    hour = int(prefs.get("morning_push_hour", 9))
    if local.hour != hour:
        return False
    last = (prefs.get("morning_push_last_sent") or "").strip()
    if last:
        try:
            last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
            if (datetime.now(timezone.utc) - last_dt).total_seconds() < 20 * 3600:
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


def send_morning_for_user(user_id: int) -> dict:
    from backend import youtube as yt

    prefs = now_plan.get_prefs(user_id)
    if prefs.get("morning_push_enabled") is False:
        return {"ok": True, "sent": 0, "skipped": "disabled"}
    pick = now_plan.pick_for_morning_push(user_id)
    if not pick:
        return {"ok": True, "sent": 0, "skipped": "empty"}
    vid = str(pick.get("video_id") or "").strip()
    if not vid:
        return {"ok": True, "sent": 0, "skipped": "no_video_id"}
    row = db.fetchone(
        """
        SELECT v.video_id, v.title, v.channel_title, li.status
        FROM library_items li
        JOIN videos v ON v.video_id = li.video_id
        WHERE li.user_id = ? AND li.video_id = ?
          AND li.status IN ('queue', 'in_progress')
        """,
        (user_id, vid),
    )
    if not row or yt.is_unavailable_video(row.get("title")):
        return {"ok": True, "sent": 0, "skipped": "unavailable"}
    name = (pick.get("title") or row.get("title") or "Ролик из очереди").strip()[:100]
    why = (pick.get("reason") or "").strip()
    push_title = name
    push_body = why if why else "На утро из вашей очереди"
    result = push.send_to_user(
        user_id,
        title=push_title,
        body=push_body[:400],
        data={
            "type": "morning",
            "video_id": vid,
            "video_title": name[:200],
            "title": push_title[:120],
            "body": push_body[:400],
            "route": f"/v/{vid}",
            "deeplink": f"clipqueue://video/{vid}?surface=morning&action=open",
            "actions": "open,not_interested",
        },
        data_only=True,
    )
    now_plan.set_prefs(
        user_id,
        {"morning_push_last_sent": datetime.now(timezone.utc).isoformat()},
    )
    if int((result or {}).get("sent") or 0) > 0:
        now_plan.record_push_sent(user_id, vid, kind="morning")
    return {
        "ok": True,
        "sent": int((result or {}).get("sent") or 0),
        "video_id": vid,
        "push": result,
    }


def tick() -> dict:
    """Scan users: weekly digest, morning push, due reminders."""
    from backend import reminders_svc

    users = db.fetchall("SELECT id FROM users LIMIT 5000")
    dig_sent = 0
    morning_sent = 0
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
        if should_send_morning(prefs, now=now):
            try:
                r = send_morning_for_user(uid)
                morning_sent += int(r.get("sent") or 0)
            except Exception as e:
                log.warning("morning push user=%s: %s", uid, e)
        if in_quiet_hours(prefs, now=now):
            continue
        try:
            due = reminders_svc.due_reminders(uid)
            for item in due[:1]:
                vid = str(item.get("video_id") or "").strip()
                if not vid:
                    continue
                vtitle = (item.get("title") or "Ролик ждёт вас").strip()[:120]
                push.send_to_user(
                    uid,
                    title=vtitle,
                    body="Напоминание Kyro",
                    data={
                        "type": "reminder",
                        "video_id": vid,
                        "video_title": vtitle[:200],
                        "title": vtitle[:120],
                        "body": "Напоминание Kyro",
                        "route": f"/v/{vid}",
                        "deeplink": f"clipqueue://video/{vid}?surface=reminder&action=open",
                    },
                    data_only=True,
                )
                reminders_svc.complete_reminder(uid, int(item["id"]))
                rem_sent += 1
        except Exception as e:
            log.warning("reminder user=%s: %s", uid, e)
    return {
        "ok": True,
        "digest_pushes": dig_sent,
        "morning_pushes": morning_sent,
        "reminder_pushes": rem_sent,
    }


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
