"""Bulk-stamp tags from folder titles + heuristics. One/few SQL round-trips."""
from __future__ import annotations

import re
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from backend import db, organize, llm  # noqa: E402

# use organize._folder_title_as_tag


def ensure_tag_id(user_id: int, name: str) -> int:
    row = db.fetchone(
        "SELECT id FROM user_tags WHERE user_id = ? AND name = ?",
        (user_id, name),
    )
    if row:
        return int(row["id"])
    # case-insensitive
    for r in db.fetchall("SELECT id, name FROM user_tags WHERE user_id = ?", (user_id,)):
        if (r.get("name") or "").lower() == name.lower():
            return int(r["id"])
    if db.is_postgres():
        with db.connect() as conn:
            cur = conn.execute(
                "INSERT INTO user_tags (user_id, name, emoji) VALUES (%s, %s, %s) "
                "RETURNING id",
                (user_id, name, ""),
            )
            return int(cur.fetchone()["id"])
    db.execute(
        "INSERT INTO user_tags (user_id, name, emoji) VALUES (?, ?, ?)",
        (user_id, name, ""),
    )
    row = db.fetchone(
        "SELECT id FROM user_tags WHERE user_id = ? AND name = ?",
        (user_id, name),
    )
    return int(row["id"])


def stamp_folder(user_id: int, list_id: int, tag_id: int) -> int:
    if db.is_postgres():
        with db.connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO item_tags (user_id, video_id, tag_id)
                SELECT %s, li.video_id, %s
                FROM list_items li
                WHERE li.list_id = %s
                  AND NOT EXISTS (
                    SELECT 1 FROM item_tags it
                    WHERE it.user_id = %s AND it.video_id = li.video_id
                      AND it.tag_id = %s
                  )
                ON CONFLICT DO NOTHING
                """,
                (user_id, tag_id, list_id, user_id, tag_id),
            )
            return cur.rowcount or 0
    # sqlite fallback — row by row
    n = 0
    rows = db.fetchall("SELECT video_id FROM list_items WHERE list_id = ?", (list_id,))
    for r in rows:
        try:
            db.execute(
                "INSERT INTO item_tags (user_id, video_id, tag_id) VALUES (?, ?, ?) "
                "ON CONFLICT(user_id, video_id, tag_id) DO NOTHING",
                (user_id, r["video_id"], tag_id),
            )
            n += 1
        except Exception:
            pass
    return n


def stamp_heuristic(user_id: int, limit: int = 2000) -> dict:
    """Apply heuristic tags to untagged library items in batches."""
    rows = db.fetchall(
        """
        SELECT li.video_id, v.title, v.channel_title, v.description
        FROM library_items li
        JOIN videos v ON v.video_id = li.video_id
        WHERE li.user_id = ?
          AND NOT EXISTS (
            SELECT 1 FROM item_tags it
            WHERE it.user_id = li.user_id AND it.video_id = li.video_id
          )
        ORDER BY li.saved_at DESC
        LIMIT ?
        """,
        (user_id, limit),
    )
    # cache tag ids
    tag_ids: dict[str, int] = {}
    stamped = 0
    tagged_videos = 0
    values: list[tuple] = []
    for r in rows:
        tags = llm._heuristic_tags(
            r.get("title") or "",
            r.get("channel_title") or "",
            r.get("description") or "",
        )
        if not tags:
            continue
        tagged_videos += 1
        for name in tags[:3]:
            if name not in tag_ids:
                tag_ids[name] = ensure_tag_id(user_id, name)
            values.append((user_id, r["video_id"], tag_ids[name]))
    # bulk insert
    if values and db.is_postgres():
        with db.connect() as conn:
            cur = conn.cursor()
            cur.executemany(
                "INSERT INTO item_tags (user_id, video_id, tag_id) VALUES (%s, %s, %s) "
                "ON CONFLICT DO NOTHING",
                values,
            )
            stamped = len(values)
    else:
        for triple in values:
            try:
                db.execute(
                    "INSERT INTO item_tags (user_id, video_id, tag_id) VALUES (?, ?, ?) "
                    "ON CONFLICT(user_id, video_id, tag_id) DO NOTHING",
                    triple,
                )
                stamped += 1
            except Exception:
                pass
    return {
        "scanned": len(rows),
        "videos_with_heuristic": tagged_videos,
        "inserts": stamped,
        "tags": sorted(tag_ids),
    }


def main() -> int:
    uid = 2
    for a in sys.argv[1:]:
        if a.startswith("--uid="):
            uid = int(a.split("=", 1)[1])
    db.init_db()
    print("folders…", flush=True)
    folders = db.fetchall("SELECT id, title FROM lists WHERE user_id = ?", (uid,))
    folder_n = 0
    used_names: set[str] = set()
    for f in folders:
        name = organize._folder_title_as_tag(f.get("title") or "")
        if not name:
            continue
        tid = ensure_tag_id(uid, name)
        n = stamp_folder(uid, int(f["id"]), tid)
        if n:
            print(f"  {name!r}: +{n}", flush=True)
            folder_n += n
            used_names.add(name)
    print("folder_stamps", folder_n, flush=True)
    print("heuristics…", flush=True)
    h = stamp_heuristic(uid, limit=3000)
    print(h, flush=True)
    used = db.fetchall(
        """
        SELECT t.name, COUNT(it.video_id) AS c
        FROM user_tags t
        JOIN item_tags it ON it.tag_id = t.id AND it.user_id = t.user_id
        WHERE t.user_id = ?
        GROUP BY t.id, t.name
        HAVING COUNT(it.video_id) > 0
        ORDER BY COUNT(it.video_id) DESC
        """,
        (uid,),
    )
    print("USED", len(used), flush=True)
    for t in used:
        print(f"  {t['name']}: {t['c']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
