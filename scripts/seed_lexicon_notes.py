"""Synthetic personal-lexicon smoke: pick sample videos and invent user notes via LLM.

Usage (local, with DATABASE_URL + OPENROUTER_API_KEY in .env):
  python -m scripts.seed_lexicon_notes --user-email you@mail.com --dry-run
  python -m scripts.seed_lexicon_notes --user-email you@mail.com --apply
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from backend import db, llm  # noqa: E402


SAMPLES = [
    "хуйня для деградантов",
    "уют на вечер",
    "стрёмная страшная хрень",
    "ржака но не стендап",
    "серьёзный вайб / думалка",
    "фоном пока готовлю",
    "про беременна в 16 и похожие шоу",
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user-email", required=True)
    ap.add_argument("--limit", type=int, default=12)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    if not args.dry_run and not args.apply:
        args.dry_run = True

    db.init_db()
    user = db.fetchone("SELECT id, email FROM users WHERE email = ?", (args.user_email,))
    if not user:
        print("user not found", args.user_email)
        sys.exit(1)
    uid = int(user["id"])
    rows = db.fetchall(
        """
        SELECT v.video_id, v.title, v.channel_title,
               substr(coalesce(v.description,''), 1, 280) AS desc_short,
               li.note
        FROM library_items li
        JOIN videos v ON v.video_id = li.video_id
        WHERE li.user_id = ?
          AND coalesce(li.status,'queue') NOT IN ('dismissed','rejected')
          AND (li.note IS NULL OR li.note = '')
        ORDER BY li.saved_at DESC
        LIMIT ?
        """,
        (uid, args.limit),
    )

    print(f"user={uid} candidates={len(rows)} llm={llm.available()}")
    for i, r in enumerate(rows):
        title = r["title"] or ""
        channel = r["channel_title"] or ""
        note = None
        if llm.available():
            data = llm.chat_json(
                "Ты пишешь короткую личную пометку зрителя к YouTube-ролику "
                "(сленг, эмоция, зачем смотреть). 3–8 слов на русском. "
                "JSON: {\"note\": \"...\"}",
                f"title={title}\nchannel={channel}\ndesc={r.get('desc_short') or ''}",
                temperature=0.7,
                timeout=15,
                max_models=2,
            )
            if data and data.get("note"):
                note = str(data["note"]).strip()[:120]
        if not note:
            note = SAMPLES[i % len(SAMPLES)]
        print(f"- {r['video_id']}: {title[:60]!r} → {note!r}")
        if args.apply:
            db.execute(
                "UPDATE library_items SET note = ? WHERE user_id = ? AND video_id = ?",
                (note, uid, r["video_id"]),
            )
    if args.apply:
        print("applied")
    else:
        print("dry-run only (pass --apply to write)")


if __name__ == "__main__":
    main()
