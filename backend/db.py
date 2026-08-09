"""SQLite locally / Postgres on Railway. No shared DB with Movie Planner."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional


def _database_url() -> str:
    return (os.environ.get("DATABASE_URL") or "sqlite:///./data/clip_queue.db").strip()


def is_postgres() -> bool:
    u = _database_url().lower()
    return u.startswith("postgres://") or u.startswith("postgresql://")


def _pg_dsn() -> str:
    url = _database_url()
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


def _sqlite_path() -> Path:
    url = _database_url()
    if url.startswith("sqlite:///"):
        raw = url[len("sqlite:///") :]
    else:
        raw = "./data/clip_queue.db"
    path = Path(raw)
    if not path.is_absolute():
        root = Path(__file__).resolve().parent.parent
        path = (root / path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


@contextmanager
def connect() -> Iterator[Any]:
    if is_postgres():
        import psycopg
        from psycopg.rows import dict_row

        conn = psycopg.connect(_pg_dsn(), row_factory=dict_row)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    else:
        conn = sqlite3.connect(str(_sqlite_path()), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def execute(sql: str, params: tuple | list = ()) -> None:
    sql = _adapt_sql(sql)
    with connect() as conn:
        conn.execute(sql, params)


def fetchone(sql: str, params: tuple | list = ()) -> Optional[dict]:
    sql = _adapt_sql(sql)
    with connect() as conn:
        cur = conn.execute(sql, params)
        row = cur.fetchone()
        return _row(row)


def fetchall(sql: str, params: tuple | list = ()) -> list[dict]:
    sql = _adapt_sql(sql)
    with connect() as conn:
        cur = conn.execute(sql, params)
        return [_row(r) for r in cur.fetchall() if r is not None]


def _row(row: Any) -> Optional[dict]:
    if row is None:
        return None
    if isinstance(row, dict):
        return dict(row)
    if hasattr(row, "keys"):
        return {k: row[k] for k in row.keys()}
    return dict(row)


def _adapt_sql(sql: str) -> str:
    if is_postgres():
        return sql.replace("?", "%s")
    return sql


def _statements(schema: str) -> list[str]:
    parts = []
    for chunk in schema.split(";"):
        s = chunk.strip()
        if s:
            parts.append(s)
    return parts


SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL UNIQUE,
  name TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
  token TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS magic_codes (
  email TEXT NOT NULL PRIMARY KEY,
  code TEXT NOT NULL,
  expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS videos (
  video_id TEXT PRIMARY KEY,
  title TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT '',
  channel_id TEXT NOT NULL DEFAULT '',
  channel_title TEXT NOT NULL DEFAULT '',
  duration_sec INTEGER,
  published_at TEXT,
  thumb_url TEXT NOT NULL DEFAULT '',
  tags_json TEXT NOT NULL DEFAULT '[]',
  fetched_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS library_items (
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  video_id TEXT NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'queue',
  note TEXT NOT NULL DEFAULT '',
  source TEXT NOT NULL DEFAULT 'paste',
  saved_at TEXT NOT NULL DEFAULT (datetime('now')),
  watched_at TEXT,
  PRIMARY KEY (user_id, video_id)
);

CREATE TABLE IF NOT EXISTS user_tags (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  emoji TEXT NOT NULL DEFAULT '',
  color TEXT NOT NULL DEFAULT '#ff3b30',
  UNIQUE(user_id, name)
);

CREATE TABLE IF NOT EXISTS item_tags (
  user_id INTEGER NOT NULL,
  video_id TEXT NOT NULL,
  tag_id INTEGER NOT NULL REFERENCES user_tags(id) ON DELETE CASCADE,
  PRIMARY KEY (user_id, video_id, tag_id)
);

CREATE TABLE IF NOT EXISTS lists (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS list_items (
  list_id INTEGER NOT NULL REFERENCES lists(id) ON DELETE CASCADE,
  video_id TEXT NOT NULL,
  position INTEGER NOT NULL DEFAULT 0,
  added_at TEXT NOT NULL DEFAULT (datetime('now')),
  PRIMARY KEY (list_id, video_id)
);

CREATE TABLE IF NOT EXISTS reminders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  video_id TEXT NOT NULL,
  remind_at TEXT NOT NULL,
  done INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS watch_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  video_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_library_user_status ON library_items(user_id, status, saved_at);
CREATE INDEX IF NOT EXISTS idx_watch_events_user ON watch_events(user_id, at);
"""


SCHEMA_PG = """
CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  name TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sessions (
  token TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS magic_codes (
  email TEXT NOT NULL PRIMARY KEY,
  code TEXT NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS videos (
  video_id TEXT PRIMARY KEY,
  title TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT '',
  channel_id TEXT NOT NULL DEFAULT '',
  channel_title TEXT NOT NULL DEFAULT '',
  duration_sec INTEGER,
  published_at TEXT,
  thumb_url TEXT NOT NULL DEFAULT '',
  tags_json TEXT NOT NULL DEFAULT '[]',
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS library_items (
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  video_id TEXT NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'queue',
  note TEXT NOT NULL DEFAULT '',
  source TEXT NOT NULL DEFAULT 'paste',
  saved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  watched_at TIMESTAMPTZ,
  PRIMARY KEY (user_id, video_id)
);

CREATE TABLE IF NOT EXISTS user_tags (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  emoji TEXT NOT NULL DEFAULT '',
  color TEXT NOT NULL DEFAULT '#ff3b30',
  UNIQUE(user_id, name)
);

CREATE TABLE IF NOT EXISTS item_tags (
  user_id INTEGER NOT NULL,
  video_id TEXT NOT NULL,
  tag_id INTEGER NOT NULL REFERENCES user_tags(id) ON DELETE CASCADE,
  PRIMARY KEY (user_id, video_id, tag_id)
);

CREATE TABLE IF NOT EXISTS lists (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS list_items (
  list_id INTEGER NOT NULL REFERENCES lists(id) ON DELETE CASCADE,
  video_id TEXT NOT NULL,
  position INTEGER NOT NULL DEFAULT 0,
  added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (list_id, video_id)
);

CREATE TABLE IF NOT EXISTS reminders (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  video_id TEXT NOT NULL,
  remind_at TIMESTAMPTZ NOT NULL,
  done INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS watch_events (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  video_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_library_user_status ON library_items(user_id, status, saved_at);
CREATE INDEX IF NOT EXISTS idx_watch_events_user ON watch_events(user_id, at);
"""

EXTRA_SQLITE = """
CREATE TABLE IF NOT EXISTS oauth_states (
  state TEXT PRIMARY KEY,
  expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS google_tokens (
  user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  access_token TEXT NOT NULL,
  refresh_token TEXT NOT NULL DEFAULT '',
  expires_at TEXT NOT NULL,
  scope TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS subscriptions (
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  channel_id TEXT NOT NULL,
  channel_title TEXT NOT NULL DEFAULT '',
  thumb_url TEXT NOT NULL DEFAULT '',
  PRIMARY KEY (user_id, channel_id)
);
CREATE TABLE IF NOT EXISTS sync_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'ok',
  stats_json TEXT NOT NULL DEFAULT '{}',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS organize_proposals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  proposal_json TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  applied INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS save_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  video_id TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT '',
  title TEXT NOT NULL DEFAULT '',
  channel_title TEXT NOT NULL DEFAULT '',
  thumb_url TEXT NOT NULL DEFAULT '',
  classified_json TEXT NOT NULL DEFAULT '[]',
  tags_json TEXT NOT NULL DEFAULT '[]',
  lists_json TEXT NOT NULL DEFAULT '[]',
  classify_engine TEXT NOT NULL DEFAULT '',
  classify_reason TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_save_events_user ON save_events(user_id, created_at DESC);
CREATE TABLE IF NOT EXISTS device_tokens (
  token TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  platform TEXT NOT NULL DEFAULT 'android',
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_device_tokens_user ON device_tokens(user_id);
"""

EXTRA_PG = """
CREATE TABLE IF NOT EXISTS oauth_states (
  state TEXT PRIMARY KEY,
  expires_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS google_tokens (
  user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  access_token TEXT NOT NULL,
  refresh_token TEXT NOT NULL DEFAULT '',
  expires_at TIMESTAMPTZ NOT NULL,
  scope TEXT NOT NULL DEFAULT '',
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS subscriptions (
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  channel_id TEXT NOT NULL,
  channel_title TEXT NOT NULL DEFAULT '',
  thumb_url TEXT NOT NULL DEFAULT '',
  PRIMARY KEY (user_id, channel_id)
);
CREATE TABLE IF NOT EXISTS sync_runs (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kind TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'ok',
  stats_json TEXT NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS organize_proposals (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  proposal_json TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  applied INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS save_events (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  video_id TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT '',
  title TEXT NOT NULL DEFAULT '',
  channel_title TEXT NOT NULL DEFAULT '',
  thumb_url TEXT NOT NULL DEFAULT '',
  classified_json TEXT NOT NULL DEFAULT '[]',
  tags_json TEXT NOT NULL DEFAULT '[]',
  lists_json TEXT NOT NULL DEFAULT '[]',
  classify_engine TEXT NOT NULL DEFAULT '',
  classify_reason TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_save_events_user ON save_events(user_id, created_at DESC);
CREATE TABLE IF NOT EXISTS device_tokens (
  token TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  platform TEXT NOT NULL DEFAULT 'android',
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_device_tokens_user ON device_tokens(user_id);
"""


def _migrate_columns() -> None:
    alters = [
        "ALTER TABLE users ADD COLUMN google_sub TEXT",
        "ALTER TABLE subscriptions ADD COLUMN thumb_url TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE library_items ADD COLUMN interest INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE lists ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 1000",
        "ALTER TABLE lists ADD COLUMN hidden_from_home INTEGER NOT NULL DEFAULT 0",
    ]
    for stmt in alters:
        try:
            with connect() as conn:
                conn.execute(stmt)
        except Exception as e:
            msg = str(e).lower()
            if "duplicate" in msg or "already exists" in msg or "exists" in msg:
                continue
            # sqlite: "duplicate column name"
            if "column" in msg and "exists" in msg:
                continue
            if "duplicate column" in msg:
                continue


def init_db() -> None:
    """Idempotent. Safe under multi-worker race on first boot."""
    schema = SCHEMA_PG if is_postgres() else SCHEMA_SQLITE
    extra = EXTRA_PG if is_postgres() else EXTRA_SQLITE
    for stmt in _statements(schema) + _statements(extra):
        try:
            with connect() as conn:
                conn.execute(stmt)
        except Exception as e:
            msg = str(e).lower()
            # Concurrent CREATE INDEX / TABLE from another worker
            if "already exists" in msg or "duplicate key" in msg or "pg_class_relname" in msg:
                continue
            raise
    _migrate_columns()
    try:
        from backend import organize

        organize.ensure_classify_tables()
    except Exception:
        pass
