#!/usr/bin/env python3
"""Live totals: Clip Queue DB + YouTube likes/playlists API."""
from __future__ import annotations

import requests

from backend import db, google_oauth


def main() -> None:
    uid = int(
        db.fetchone(
            "SELECT user_id FROM library_items GROUP BY user_id ORDER BY COUNT(*) DESC LIMIT 1"
        )["user_id"]
    )
    user = db.fetchone("SELECT id, email, name FROM users WHERE id=?", (uid,))
    print("user", dict(user) if user else uid)
    for label, sql, p in [
        ("total", "SELECT COUNT(*) AS c FROM library_items WHERE user_id=?", (uid,)),
        ("queue", "SELECT COUNT(*) AS c FROM library_items WHERE user_id=? AND status=?", (uid, "queue")),
        ("archived", "SELECT COUNT(*) AS c FROM library_items WHERE user_id=? AND status=?", (uid, "archived")),
        ("watched", "SELECT COUNT(*) AS c FROM library_items WHERE user_id=? AND status=?", (uid, "watched")),
        ("liked", "SELECT COUNT(*) AS c FROM library_items WHERE user_id=? AND source=?", (uid, "liked")),
        ("playlist", "SELECT COUNT(*) AS c FROM library_items WHERE user_id=? AND source=?", (uid, "playlist")),
    ]:
        print(label, db.fetchone(sql, p)["c"])
    print(
        "distinct",
        db.fetchone(
            "SELECT COUNT(DISTINCT video_id) AS c FROM library_items WHERE user_id=?",
            (uid,),
        )["c"],
    )

    access = google_oauth.get_valid_access_token(uid)
    h = {"Authorization": f"Bearer {access}"}
    ch = requests.get(
        "https://www.googleapis.com/youtube/v3/channels",
        params={"part": "contentDetails", "mine": "true"},
        headers=h,
        timeout=20,
    ).json()
    related = ((ch.get("items") or [{}])[0].get("contentDetails") or {}).get("relatedPlaylists") or {}
    print("related", related)
    likes_pl = related.get("likes")
    for label, pid in [("LIKES", likes_pl), ("WL", "WL")]:
        if not pid:
            print(label, "missing")
            continue
        r = requests.get(
            "https://www.googleapis.com/youtube/v3/playlistItems",
            params={"part": "id", "playlistId": pid, "maxResults": 1},
            headers=h,
            timeout=20,
        )
        data = r.json()
        print(
            label,
            r.status_code,
            "totalResults",
            (data.get("pageInfo") or {}).get("totalResults"),
            "err",
            ((data.get("error") or {}).get("message") or "")[:120],
        )

    pls: list[dict] = []
    token = None
    while True:
        params: dict = {"part": "snippet,contentDetails", "mine": "true", "maxResults": 50}
        if token:
            params["pageToken"] = token
        data = requests.get(
            "https://www.googleapis.com/youtube/v3/playlists",
            params=params,
            headers=h,
            timeout=20,
        ).json()
        pls.extend(data.get("items") or [])
        token = data.get("nextPageToken")
        if not token:
            break
    print("playlists_count", len(pls))
    s = 0
    for p in sorted(pls, key=lambda x: -int((x.get("contentDetails") or {}).get("itemCount") or 0)):
        title = (p.get("snippet") or {}).get("title")
        cnt = int((p.get("contentDetails") or {}).get("itemCount") or 0)
        s += cnt
        print("PL", cnt, "|", title, "|", p.get("id"))
    print("sum_playlist_itemCounts", s)

    n = 0
    token = None
    while likes_pl and n < 6000:
        params = {"part": "id", "playlistId": likes_pl, "maxResults": 50}
        if token:
            params["pageToken"] = token
        data = requests.get(
            "https://www.googleapis.com/youtube/v3/playlistItems",
            params=params,
            headers=h,
            timeout=30,
        ).json()
        items = data.get("items") or []
        n += len(items)
        token = data.get("nextPageToken")
        if not token or not items:
            break
    print("LIKES_paged", n)


if __name__ == "__main__":
    main()
