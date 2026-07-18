#!/usr/bin/env python3
"""Quick library mix diag for music/shorts filtering."""
from __future__ import annotations

from backend.db import connect
from backend import youtube as yt


def main() -> None:
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM library_items")
    print("library_total", cur.fetchone()[0])
    cur.execute("SELECT COUNT(*) FROM library_items WHERE source = %s", ("liked",))
    print("liked", cur.fetchone()[0])
    cur.execute(
        """
        SELECT v.title, v.channel_title, v.duration_sec, v.youtube_id
        FROM videos v
        JOIN library_items li ON li.video_id = v.id
        ORDER BY li.saved_at DESC NULLS LAST
        LIMIT 40
        """
    )
    rows = cur.fetchall()
    music = 0
    shorts = 0
    video = 0
    for title, ch, dur, yid in rows:
        m = yt.is_music_content(title, ch)
        s = yt.is_short(dur, title=title)
        bucket = "music" if m else ("shorts" if s else "video")
        if bucket == "music":
            music += 1
        elif bucket == "shorts":
            shorts += 1
        else:
            video += 1
        print(f"{bucket:6} dur={dur!s:>6} | {ch!s} | {title!s}"[:140])
    print("sample_mix", {"music": music, "shorts": shorts, "video": video})
    conn.close()


if __name__ == "__main__":
    main()
