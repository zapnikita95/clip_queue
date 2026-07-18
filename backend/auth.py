"""Email magic-link auth. Separate from Movie Planner accounts."""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from backend import db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _parse_iso(s: str) -> datetime:
    if not s:
        raise ValueError("empty")
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def get_or_create_user(email: str, name: Optional[str] = None) -> dict:
    email = normalize_email(email)
    if not email or "@" not in email:
        raise ValueError("Нужен email")
    row = db.fetchone("SELECT * FROM users WHERE email = ?", (email,))
    if row:
        return row
    display = name or email.split("@")[0]
    if db.is_postgres():
        with db.connect() as conn:
            cur = conn.execute(
                "INSERT INTO users (email, name) VALUES (%s, %s) RETURNING id, email, name, created_at",
                (email, display),
            )
            r = cur.fetchone()
            return {
                "id": r["id"],
                "email": r["email"],
                "name": r["name"],
                "created_at": str(r["created_at"]),
            }
    db.execute(
        "INSERT INTO users (email, name) VALUES (?, ?)",
        (email, display),
    )
    row = db.fetchone("SELECT * FROM users WHERE email = ?", (email,))
    assert row
    return row


def create_magic_code(email: str) -> str:
    email = normalize_email(email)
    code = f"{secrets.randbelow(1_000_000):06d}"
    expires = _iso(_utcnow() + timedelta(minutes=15))
    if db.is_postgres():
        db.execute(
            "INSERT INTO magic_codes (email, code, expires_at) VALUES (?, ?, ?) "
            "ON CONFLICT (email) DO UPDATE SET code = EXCLUDED.code, expires_at = EXCLUDED.expires_at",
            (email, code, expires),
        )
    else:
        db.execute(
            "INSERT OR REPLACE INTO magic_codes (email, code, expires_at) VALUES (?, ?, ?)",
            (email, code, expires),
        )
    return code


def verify_magic_code(email: str, code: str) -> dict:
    email = normalize_email(email)
    code = (code or "").strip()
    row = db.fetchone(
        "SELECT * FROM magic_codes WHERE email = ?",
        (email,),
    )
    if not row or row["code"] != code:
        raise ValueError("Неверный код")
    if _parse_iso(str(row["expires_at"])) < _utcnow():
        raise ValueError("Код истёк")
    db.execute("DELETE FROM magic_codes WHERE email = ?", (email,))
    user = get_or_create_user(email)
    return create_session(int(user["id"]))


def create_session(user_id: int, days: int = 60) -> dict:
    token = secrets.token_urlsafe(32)
    expires = _iso(_utcnow() + timedelta(days=days))
    db.execute(
        "INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
        (token, user_id, expires),
    )
    user = db.fetchone("SELECT * FROM users WHERE id = ?", (user_id,))
    return {"token": token, "expires_at": expires, "user": user}


def resolve_session(token: Optional[str]) -> Optional[dict]:
    if not token:
        return None
    token = token.strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    row = db.fetchone(
        "SELECT s.token, s.expires_at, u.id AS user_id, u.email, u.name "
        "FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token = ?",
        (token,),
    )
    if not row:
        return None
    if _parse_iso(str(row["expires_at"])) < _utcnow():
        db.execute("DELETE FROM sessions WHERE token = ?", (token,))
        return None
    return {
        "token": row["token"],
        "user_id": int(row["user_id"]),
        "email": row["email"],
        "name": row["name"],
    }


def destroy_session(token: str) -> None:
    db.execute("DELETE FROM sessions WHERE token = ?", (token.strip(),))


def dev_login_enabled() -> bool:
    return (os.environ.get("DEV_LOGIN") or "").strip() in ("1", "true", "yes")


def ensure_dev_user() -> dict:
    email = normalize_email(os.environ.get("DEV_EMAIL") or "dev@clipqueue.local")
    return get_or_create_user(email, name="Dev")


def session_fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:12]