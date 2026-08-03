"""Google OAuth for Clip Queue (identity + YouTube readonly)."""

from __future__ import annotations

import os
import secrets
from datetime import timedelta
from typing import Any, Optional
from urllib.parse import urlencode

import requests

from backend import auth, db

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def client_id() -> str:
    return (
        os.environ.get("GOOGLE_CLIENT_ID")
        or os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
        or ""
    ).strip()


def client_secret() -> str:
    return (
        os.environ.get("GOOGLE_CLIENT_SECRET")
        or os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
        or ""
    ).strip()


def configured() -> bool:
    return bool(client_id() and client_secret())


def public_origin() -> str:
    return (os.environ.get("PUBLIC_ORIGIN") or "http://127.0.0.1:8765").rstrip("/")


def redirect_uri() -> str:
    custom = (os.environ.get("GOOGLE_REDIRECT_URI") or "").strip()
    if custom:
        return custom
    return f"{public_origin()}/api/auth/google/callback"


def start_url(state: Optional[str] = None, *, client: Optional[str] = None) -> str:
    if not configured():
        raise RuntimeError("GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET не заданы")
    raw = state or secrets.token_urlsafe(24)
    # Encode mobile client in state so callback can deep-link back to the app.
    st = f"android.{raw}" if (client or "").strip().lower() == "android" else raw
    expires = auth._iso(auth._utcnow() + timedelta(minutes=20))
    if db.is_postgres():
        db.execute(
            "INSERT INTO oauth_states (state, expires_at) VALUES (?, ?) "
            "ON CONFLICT (state) DO UPDATE SET expires_at = EXCLUDED.expires_at",
            (st, expires),
        )
    else:
        db.execute(
            "INSERT OR REPLACE INTO oauth_states (state, expires_at) VALUES (?, ?)",
            (st, expires),
        )
    params = {
        "client_id": client_id(),
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": st,
    }
    return f"{AUTH_URL}?{urlencode(params)}"


def is_android_state(state: str) -> bool:
    return (state or "").startswith("android.")


def _consume_state(state: str) -> bool:
    row = db.fetchone("SELECT * FROM oauth_states WHERE state = ?", (state,))
    if not row:
        return False
    db.execute("DELETE FROM oauth_states WHERE state = ?", (state,))
    try:
        if auth._parse_iso(str(row["expires_at"])) < auth._utcnow():
            return False
    except Exception:
        return False
    return True


def exchange_code(code: str) -> dict[str, Any]:
    r = requests.post(
        TOKEN_URL,
        data={
            "code": code,
            "client_id": client_id(),
            "client_secret": client_secret(),
            "redirect_uri": redirect_uri(),
            "grant_type": "authorization_code",
        },
        timeout=20,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Google token error: {r.status_code} {r.text[:300]}")
    return r.json()


def refresh_access_token(refresh_token: str) -> dict[str, Any]:
    r = requests.post(
        TOKEN_URL,
        data={
            "client_id": client_id(),
            "client_secret": client_secret(),
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=20,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Google refresh error: {r.status_code} {r.text[:300]}")
    return r.json()


def fetch_userinfo(access_token: str) -> dict[str, Any]:
    r = requests.get(
        USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    if r.status_code != 200:
        raise RuntimeError(f"userinfo failed: {r.status_code}")
    return r.json()


def save_tokens(user_id: int, token_payload: dict[str, Any]) -> None:
    access = token_payload.get("access_token") or ""
    refresh = token_payload.get("refresh_token") or ""
    expires_in = int(token_payload.get("expires_in") or 3600)
    scope = token_payload.get("scope") or " ".join(SCOPES)
    expires_at = auth._iso(auth._utcnow() + timedelta(seconds=max(60, expires_in - 60)))
    existing = db.fetchone("SELECT * FROM google_tokens WHERE user_id = ?", (user_id,))
    if existing:
        if not refresh:
            refresh = existing.get("refresh_token") or ""
        db.execute(
            "UPDATE google_tokens SET access_token = ?, refresh_token = ?, expires_at = ?, scope = ? "
            "WHERE user_id = ?",
            (access, refresh, expires_at, scope, user_id),
        )
    else:
        db.execute(
            "INSERT INTO google_tokens (user_id, access_token, refresh_token, expires_at, scope) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, access, refresh, expires_at, scope),
        )


def get_valid_access_token(user_id: int) -> str:
    row = db.fetchone("SELECT * FROM google_tokens WHERE user_id = ?", (user_id,))
    if not row:
        raise RuntimeError("YouTube не подключён — войди через Google")
    try:
        if auth._parse_iso(str(row["expires_at"])) > auth._utcnow():
            return row["access_token"]
    except Exception:
        pass
    refresh = row.get("refresh_token") or ""
    if not refresh:
        raise RuntimeError("Нет refresh_token — перелогинься через Google")
    payload = refresh_access_token(refresh)
    save_tokens(user_id, {**payload, "refresh_token": refresh})
    return payload["access_token"]


def login_with_code(code: str, state: str) -> dict:
    if not _consume_state(state):
        raise ValueError("Неверный или просроченный state")
    tokens = exchange_code(code)
    info = fetch_userinfo(tokens["access_token"])
    email = auth.normalize_email(info.get("email") or "")
    if not email:
        raise ValueError("Google не вернул email")
    name = (info.get("name") or info.get("given_name") or email.split("@")[0]).strip()
    google_sub = (info.get("sub") or "").strip()
    user = auth.get_or_create_user(email, name=name)
    uid = int(user["id"])
    if google_sub:
        try:
            db.execute("UPDATE users SET google_sub = ? WHERE id = ?", (google_sub, uid))
        except Exception:
            pass
    save_tokens(uid, tokens)
    return auth.create_session(uid)


def youtube_connected(user_id: int) -> bool:
    return bool(db.fetchone("SELECT user_id FROM google_tokens WHERE user_id = ?", (user_id,)))
