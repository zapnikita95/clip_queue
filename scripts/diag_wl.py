#!/usr/bin/env python3
import requests
from backend import db, google_oauth, youtube as yt

uid = int(
    db.fetchone(
        "SELECT user_id FROM library_items GROUP BY user_id ORDER BY COUNT(*) DESC LIMIT 1"
    )["user_id"]
)
print("uid", uid)
for label, sql, p in [
    ("total", "SELECT COUNT(*) AS c FROM library_items WHERE user_id=?", (uid,)),
    ("queue", "SELECT COUNT(*) AS c FROM library_items WHERE user_id=? AND status=?", (uid, "queue")),
    ("archived", "SELECT COUNT(*) AS c FROM library_items WHERE user_id=? AND status=?", (uid, "archived")),
    ("liked", "SELECT COUNT(*) AS c FROM library_items WHERE user_id=? AND source=?", (uid, "liked")),
    ("playlist", "SELECT COUNT(*) AS c FROM library_items WHERE user_id=? AND source=?", (uid, "playlist")),
]:
    print(label, db.fetchone(sql, p)["c"])

b = db.fetchone(
    """
    SELECT COUNT(*) AS c FROM library_items li
    JOIN videos v ON v.video_id = li.video_id
    WHERE li.user_id=? AND lower(v.title) IN (?, ?, ?)
    """,
    (uid, "private video", "deleted video", "deleted video."),
)
print("broken", b["c"])

access = google_oauth.get_valid_access_token(uid)
r = requests.get(
    "https://www.googleapis.com/youtube/v3/playlistItems",
    params={"part": "id", "playlistId": "WL", "maxResults": 1},
    headers={"Authorization": f"Bearer {access}"},
    timeout=20,
)
print("WL_api", r.status_code, r.text[:240])
ch = requests.get(
    "https://www.googleapis.com/youtube/v3/channels",
    params={"part": "contentDetails", "mine": "true"},
    headers={"Authorization": f"Bearer {access}"},
    timeout=20,
).json()
rel = ((ch.get("items") or [{}])[0].get("contentDetails") or {}).get("relatedPlaylists") or {}
print("relatedPlaylists", rel)
