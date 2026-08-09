"""FCM push helpers. No-op when FIREBASE_SERVICE_ACCOUNT_JSON is unset."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

from backend import db

log = logging.getLogger("clip_queue.push")

_app_ready = False
_init_attempted = False


def _ensure_firebase() -> bool:
    global _app_ready, _init_attempted
    if _app_ready:
        return True
    if _init_attempted:
        return False
    _init_attempted = True
    raw = (os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON") or "").strip()
    path = (os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH") or "").strip()
    if not raw and not path:
        log.info("FCM disabled: set FIREBASE_SERVICE_ACCOUNT_JSON or FIREBASE_SERVICE_ACCOUNT_PATH")
        return False
    try:
        import firebase_admin
        from firebase_admin import credentials

        if firebase_admin._apps:
            _app_ready = True
            return True
        if raw:
            info = json.loads(raw)
            cred = credentials.Certificate(info)
        else:
            cred = credentials.Certificate(path)
        firebase_admin.initialize_app(cred)
        _app_ready = True
        log.info("Firebase Admin initialized for FCM")
        return True
    except Exception as e:
        log.warning("Firebase Admin init failed: %s", e)
        return False


def register_device(user_id: int, token: str, platform: str = "android") -> None:
    token = (token or "").strip()
    if not token or len(token) < 20:
        raise ValueError("Некорректный device token")
    platform = (platform or "android").strip()[:20] or "android"
    existing = db.fetchone("SELECT user_id FROM device_tokens WHERE token = ?", (token,))
    if existing:
        if db.is_postgres():
            db.execute(
                "UPDATE device_tokens SET user_id = ?, platform = ?, updated_at = NOW() "
                "WHERE token = ?",
                (user_id, platform, token),
            )
        else:
            db.execute(
                "UPDATE device_tokens SET user_id = ?, platform = ?, "
                "updated_at = datetime('now') WHERE token = ?",
                (user_id, platform, token),
            )
    else:
        db.execute(
            "INSERT INTO device_tokens (token, user_id, platform) VALUES (?, ?, ?)",
            (token, user_id, platform),
        )


def unregister_device(user_id: int, token: str) -> None:
    token = (token or "").strip()
    if not token:
        return
    db.execute(
        "DELETE FROM device_tokens WHERE user_id = ? AND token = ?",
        (user_id, token),
    )


def tokens_for_user(user_id: int) -> list[str]:
    rows = db.fetchall(
        "SELECT token FROM device_tokens WHERE user_id = ?",
        (user_id,),
    )
    return [str(r["token"]) for r in rows if r.get("token")]


def send_to_user(
    user_id: int,
    *,
    title: str,
    body: str,
    data: Optional[dict[str, str]] = None,
) -> dict[str, Any]:
    """Send notification to all registered devices. Returns send stats."""
    tokens = tokens_for_user(user_id)
    if not tokens:
        return {"ok": True, "sent": 0, "skipped": "no_tokens"}
    if not _ensure_firebase():
        log.info(
            "FCM skip (not configured) user=%s title=%r body=%r data=%s",
            user_id,
            title,
            body,
            data,
        )
        return {"ok": True, "sent": 0, "skipped": "fcm_unconfigured"}

    from firebase_admin import messaging

    payload = {k: str(v) for k, v in (data or {}).items()}
    sent = 0
    dead: list[str] = []
    errors: list[str] = []
    for token in tokens:
        try:
            msg = messaging.Message(
                token=token,
                notification=messaging.Notification(title=title[:120], body=body[:400]),
                data=payload,
                android=messaging.AndroidConfig(
                    priority="high",
                    notification=messaging.AndroidNotification(
                        channel_id="kyro_classify",
                        click_action="OPEN_VIDEO",
                    ),
                ),
            )
            messaging.send(msg)
            sent += 1
        except Exception as e:
            err = str(e)
            errors.append(err[:160])
            low = err.lower()
            if "not-found" in low or "unregistered" in low or "invalid" in low:
                dead.append(token)
            log.warning("FCM send failed user=%s: %s", user_id, e)
    for token in dead:
        try:
            db.execute("DELETE FROM device_tokens WHERE token = ?", (token,))
        except Exception:
            pass
    return {"ok": True, "sent": sent, "failed": len(errors), "errors": errors[:5]}
