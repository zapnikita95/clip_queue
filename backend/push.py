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
    if db.is_postgres():
        db.execute(
            """
            INSERT INTO device_tokens (token, user_id, platform, updated_at)
            VALUES (?, ?, ?, NOW())
            ON CONFLICT (token) DO UPDATE SET
              user_id = EXCLUDED.user_id,
              platform = EXCLUDED.platform,
              updated_at = NOW()
            """,
            (token, user_id, platform),
        )
    else:
        db.execute(
            """
            INSERT INTO device_tokens (token, user_id, platform, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(token) DO UPDATE SET
              user_id = excluded.user_id,
              platform = excluded.platform,
              updated_at = datetime('now')
            """,
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
    data_only: bool = False,
) -> dict[str, Any]:
    """Send notification to all registered devices. Returns send stats.

    data_only=True (default for video pushes): no FCM ``notification`` payload so
    Android always delivers to KyroMessagingService, which builds a local notif
    with a reliable clipqueue:// PendingIntent + action buttons. Tray-only FCM
    notifications often drop extras / ignore click on OEM skins (Huawei).
    """
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
    vid = (payload.get("video_id") or "").strip()
    if vid and "deeplink" not in payload:
        payload["deeplink"] = f"clipqueue://video/{vid}?surface=push"
    if vid and "route" not in payload:
        payload["route"] = f"/v/{vid}"
    # Title/body in data so the app can render when data_only.
    payload.setdefault("title", (title or "Kyro")[:120])
    payload.setdefault("body", (body or "")[:400])

    # Video-related pushes → data-only for reliable open + actions.
    kind = (payload.get("type") or "").strip().lower()
    if vid or kind in ("morning", "classify", "classified", "reminder", "share"):
        data_only = True

    sent = 0
    dead: list[str] = []
    errors: list[str] = []
    for token in tokens:
        try:
            if data_only:
                msg = messaging.Message(
                    token=token,
                    data=payload,
                    android=messaging.AndroidConfig(priority="high"),
                )
            else:
                msg = messaging.Message(
                    token=token,
                    notification=messaging.Notification(title=title[:120], body=body[:400]),
                    data=payload,
                    android=messaging.AndroidConfig(
                        priority="high",
                        notification=messaging.AndroidNotification(
                            channel_id="kyro_classify",
                            click_action="OPEN_MAIN",
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
    return {"ok": True, "sent": sent, "failed": len(errors), "errors": errors[:5], "data_only": data_only}
