"""Inspect users/tags and optionally retag untagged library videos."""
from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

# Ensure repo import works when run as a script
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend import db, organize  # noqa: E402


def main() -> int:
    db.init_db()
    do_retag = "--retag" in sys.argv
    uid_arg = None
    limit = 120
    for a in sys.argv[1:]:
        if a.startswith("--uid="):
            uid_arg = int(a.split("=", 1)[1])
        if a.startswith("--limit="):
            limit = int(a.split("=", 1)[1])

    users = db.fetchall("SELECT id, email FROM users ORDER BY id")
    print("users", len(users), flush=True)
    main_uid = uid_arg
    main_score = -1
    for u in users:
        uid = int(u["id"])
        lib = db.fetchone(
            "SELECT COUNT(*) AS c FROM library_items WHERE user_id = ?", (uid,)
        )
        lists = db.fetchone("SELECT COUNT(*) AS c FROM lists WHERE user_id = ?", (uid,))
        items = db.fetchone(
            "SELECT COUNT(*) AS c FROM list_items li "
            "JOIN lists l ON l.id = li.list_id WHERE l.user_id = ?",
            (uid,),
        )
        used = db.fetchone(
            """
            SELECT COUNT(*) AS c FROM (
              SELECT t.id
              FROM user_tags t
              JOIN item_tags it ON it.tag_id = t.id AND it.user_id = t.user_id
              WHERE t.user_id = ?
              GROUP BY t.id
              HAVING COUNT(it.video_id) > 0
            ) x
            """,
            (uid,),
        )
        untagged = db.fetchone(
            """
            SELECT COUNT(*) AS c FROM library_items li
            WHERE li.user_id = ?
              AND NOT EXISTS (
                SELECT 1 FROM item_tags it
                WHERE it.user_id = li.user_id AND it.video_id = li.video_id
              )
            """,
            (uid,),
        )
        score = int((lib or {}).get("c") or 0) + int((items or {}).get("c") or 0)
        print(
            f"id={uid} email={u.get('email')} lib={(lib or {}).get('c')} "
            f"lists={(lists or {}).get('c')} list_items={(items or {}).get('c')} "
            f"used_tags={(used or {}).get('c')} untagged_lib={(untagged or {}).get('c')}",
            flush=True,
        )
        tags = db.fetchall(
            """
            SELECT t.name, COUNT(it.video_id) AS c
            FROM user_tags t
            LEFT JOIN item_tags it ON it.tag_id = t.id AND it.user_id = t.user_id
            WHERE t.user_id = ?
            GROUP BY t.id, t.name
            ORDER BY COUNT(it.video_id) DESC, t.name
            LIMIT 20
            """,
            (uid,),
        )
        print(" tags", [(t["name"], t["c"]) for t in tags], flush=True)
        if uid_arg is None and score > main_score:
            main_score = score
            main_uid = uid

    if do_retag and main_uid is not None:
        print("RETAG uid", main_uid, "limit", limit, flush=True)
        result = organize.retag_library_batch(
            main_uid, limit=limit, use_llm=True, llm_budget=min(60, limit)
        )
        print(result, flush=True)
        used2 = db.fetchall(
            """
            SELECT t.name, COUNT(it.video_id) AS c
            FROM user_tags t
            JOIN item_tags it ON it.tag_id = t.id AND it.user_id = t.user_id
            WHERE t.user_id = ?
            GROUP BY t.id, t.name
            HAVING COUNT(it.video_id) > 0
            ORDER BY COUNT(it.video_id) DESC
            """,
            (main_uid,),
        )
        print("used_after", len(used2), [(t["name"], t["c"]) for t in used2], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
