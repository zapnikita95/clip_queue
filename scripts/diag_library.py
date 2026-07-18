"""Run inside Railway: python3 scripts/diag_library.py"""
from backend import db

uid = 2
print("by source", db.fetchall(
    "SELECT COUNT(*) AS c, source FROM library_items WHERE user_id = ? GROUP BY source",
    (uid,),
))
print("total", db.fetchone("SELECT COUNT(*) AS c FROM library_items WHERE user_id = ?", (uid,)))
print("top channels:")
for r in db.fetchall(
    """
    SELECT v.channel_title, COUNT(*) AS c FROM library_items li
    JOIN videos v ON v.video_id = li.video_id
    WHERE li.user_id = ?
    GROUP BY v.channel_title ORDER BY c DESC LIMIT 25
    """,
    (uid,),
):
    print(f"  {r['c']:4d}  {r['channel_title']}")
print("lists:")
for l in db.fetchall("SELECT id, title FROM lists WHERE user_id = ? ORDER BY id", (uid,)):
    n = db.fetchone("SELECT COUNT(*) AS c FROM list_items WHERE list_id = ?", (l["id"],))
    print(f"  [{n['c']}] {l['title']}")
if db.is_postgres():
    print("topic", db.fetchone(
        """
        SELECT COUNT(*) AS c FROM library_items li
        JOIN videos v ON v.video_id = li.video_id
        WHERE li.user_id = ? AND v.channel_title ILIKE %s
        """,
        (uid, "%Topic"),
    ))
    print("non_topic", db.fetchone(
        """
        SELECT COUNT(*) AS c FROM library_items li
        JOIN videos v ON v.video_id = li.video_id
        WHERE li.user_id = ? AND (v.channel_title IS NULL OR v.channel_title NOT ILIKE %s)
        """,
        (uid, "%Topic"),
    ))
