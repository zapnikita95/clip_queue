"""Remove junk tags stamped from YT dump playlists / catchalls."""
from __future__ import annotations

import re
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

from backend import db  # noqa: E402

JUNK = re.compile(
    r"(лайки|likes youtube|discover weekly|микс дня|release radar|daily mix|"
    r"в очереди|очередь|смотреть позже|watch later|listen later|"
    r"короткие|длинные|музыка\s*/\s*клипы|all videos|все видео|"
    r"неразобран|прочее|другое|inbox|сомтреть|"
    r"^канал:|^тема:|^yt:|"
    r"emo kids|rock em all|to stay alive|^myself$|what i play|"
    r"abstract backgrounds|подборка|wedding|танцевальное|"
    r"^буги$|^meditate$|фемки)",
    re.I,
)


def is_junk(name: str) -> bool:
    from backend.llm import CLASSIFY_THEME_TAGS

    n = (name or "").strip()
    if not n:
        return True
    low = n.lower()
    # Keep canonical themes always
    if low in CLASSIFY_THEME_TAGS:
        return False
    if JUNK.search(n):
        return True
    if low.startswith(("канал:", "тема:", "yt:")):
        return True
    if "(" in n and ("мин" in low or "до" in low):
        return True
    # Anything not a known theme — drop playlist leftovers
    aliases = {
        "кино и сериалы",
        "еда и готовка",
        "бизнес и деньги",
        "про языки",
    }
    if low in aliases:
        return True  # remapped to short themes on next stamp
    if len(n) > 28 or len(n.split()) >= 3:
        return True
    # unknown short personal playlist names
    if low not in CLASSIFY_THEME_TAGS:
        return True
    return False


def main() -> int:
    uid = 2
    for a in sys.argv[1:]:
        if a.startswith("--uid="):
            uid = int(a.split("=", 1)[1])
    db.init_db()
    tags = db.fetchall(
        "SELECT id, name FROM user_tags WHERE user_id = ?", (uid,)
    )
    removed = 0
    for t in tags:
        if not is_junk(t.get("name") or ""):
            continue
        tid = int(t["id"])
        db.execute(
            "DELETE FROM item_tags WHERE user_id = ? AND tag_id = ?",
            (uid, tid),
        )
        db.execute("DELETE FROM user_tags WHERE id = ? AND user_id = ?", (tid, uid))
        print(f"removed {t['name']!r}", flush=True)
        removed += 1
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
    print("removed", removed, "USED", len(used), flush=True)
    for t in used:
        print(f"  {t['name']}: {t['c']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
