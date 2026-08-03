"""Fast heuristic+folder retag for a user (no LLM)."""
from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from backend import db, organize  # noqa: E402


def main() -> int:
    uid = 2
    limit = 800
    for a in sys.argv[1:]:
        if a.startswith("--uid="):
            uid = int(a.split("=", 1)[1])
        if a.startswith("--limit="):
            limit = int(a.split("=", 1)[1])
    db.init_db()
    print(f"fast retag uid={uid} limit={limit}", flush=True)
    result = organize.retag_library_batch(uid, limit=limit, use_llm=False, llm_budget=0)
    print(result, flush=True)
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
    print("used_tags", len(used), flush=True)
    for t in used:
        print(f"  {t['name']}: {t['c']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
