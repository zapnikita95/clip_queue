"""Resolve YouTube URLs → metadata. oEmbed first; Data API optional."""

from __future__ import annotations

import json
import os
import re
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

import requests

YT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,20}$")


def extract_video_id(url_or_id: str) -> Optional[str]:
    raw = (url_or_id or "").strip()
    if not raw:
        return None
    if YT_ID_RE.match(raw) and "://" not in raw and "/" not in raw:
        return raw

    if "://" not in raw:
        raw = "https://" + raw

    try:
        u = urlparse(raw)
    except Exception:
        return None

    host = (u.netloc or "").lower().replace("www.", "")
    path = u.path or ""

    if host in ("youtu.be", "m.youtu.be"):
        vid = path.strip("/").split("/")[0]
        return vid if YT_ID_RE.match(vid) else None

    if "youtube.com" in host or host.endswith("youtube-nocookie.com"):
        qs = parse_qs(u.query or "")
        if "v" in qs and qs["v"]:
            vid = qs["v"][0]
            return vid if YT_ID_RE.match(vid) else None
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 2 and parts[0] in ("shorts", "embed", "live", "v"):
            vid = parts[1]
            return vid if YT_ID_RE.match(vid) else None

    return None


def thumb_url(video_id: str) -> str:
    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"


def watch_url(video_id: str) -> str:
    return f"https://www.youtube.com/watch?v={video_id}"


def _oembed(video_id: str) -> dict[str, Any]:
    url = watch_url(video_id)
    r = requests.get(
        "https://www.youtube.com/oembed",
        params={"url": url, "format": "json"},
        timeout=8,
        headers={"User-Agent": "ClipQueue/0.1"},
    )
    if r.status_code != 200:
        raise RuntimeError(f"oEmbed failed: HTTP {r.status_code}")
    data = r.json()
    return {
        "video_id": video_id,
        "title": (data.get("title") or "").strip() or f"YouTube {video_id}",
        "description": "",
        "channel_id": "",
        "channel_title": (data.get("author_name") or "").strip(),
        "duration_sec": None,
        "published_at": None,
        "thumb_url": (data.get("thumbnail_url") or "").strip() or thumb_url(video_id),
        "tags": [],
        "source": "oembed",
    }


def _iso8601_duration_to_sec(s: str) -> Optional[int]:
    if not s or not s.startswith("PT"):
        return None
    h = m = sec = 0
    mh = re.search(r"(\d+)H", s)
    mm = re.search(r"(\d+)M", s)
    ms = re.search(r"(\d+)S", s)
    if mh:
        h = int(mh.group(1))
    if mm:
        m = int(mm.group(1))
    if ms:
        sec = int(ms.group(1))
    return h * 3600 + m * 60 + sec


def _data_api(video_id: str) -> Optional[dict[str, Any]]:
    key = (os.environ.get("YOUTUBE_API_KEY") or "").strip()
    if not key:
        return None
    r = requests.get(
        "https://www.googleapis.com/youtube/v3/videos",
        params={
            "id": video_id,
            "part": "snippet,contentDetails",
            "key": key,
        },
        timeout=10,
    )
    if r.status_code != 200:
        return None
    items = (r.json() or {}).get("items") or []
    if not items:
        return None
    item = items[0]
    sn = item.get("snippet") or {}
    thumbs = sn.get("thumbnails") or {}
    thumb = ""
    for k in ("maxres", "standard", "high", "medium", "default"):
        if k in thumbs and thumbs[k].get("url"):
            thumb = thumbs[k]["url"]
            break
    return {
        "video_id": video_id,
        "title": (sn.get("title") or "").strip() or f"YouTube {video_id}",
        "description": (sn.get("description") or "").strip(),
        "channel_id": (sn.get("channelId") or "").strip(),
        "channel_title": (sn.get("channelTitle") or "").strip(),
        "duration_sec": _iso8601_duration_to_sec(
            ((item.get("contentDetails") or {}).get("duration") or "")
        ),
        "published_at": sn.get("publishedAt"),
        "thumb_url": thumb or thumb_url(video_id),
        "tags": list(sn.get("tags") or [])[:40],
        "source": "youtube_api",
    }


def resolve(url_or_id: str) -> dict[str, Any]:
    video_id = extract_video_id(url_or_id)
    if not video_id:
        raise ValueError("Не похоже на ссылку YouTube")
    meta = _data_api(video_id)
    if meta:
        return meta
    return _oembed(video_id)


def format_duration(sec: Optional[int]) -> str:
    if sec is None or sec < 0:
        return ""
    h, rem = divmod(int(sec), 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def is_music_topic_channel(channel_title: str | None) -> bool:
    t = (channel_title or "").strip().lower()
    return t.endswith(" - topic") or t.endswith(" topic") or t == "topic"


def is_unavailable_video(title: str | None) -> bool:
    t = (title or "").strip().lower()
    return t in ("deleted video", "private video", "deleted video.")


def card_from_video_row(row: dict, extra: Optional[dict] = None) -> dict:
    tags = []
    try:
        tags = json.loads(row.get("tags_json") or "[]")
    except Exception:
        tags = []
    title = row.get("title") or ""
    channel_title = row.get("channel_title") or ""
    out = {
        "video_id": row["video_id"],
        "title": title,
        "description": row.get("description") or "",
        "channel_id": row.get("channel_id") or "",
        "channel_title": channel_title,
        "duration_sec": row.get("duration_sec"),
        "duration_label": format_duration(row.get("duration_sec")),
        "published_at": row.get("published_at"),
        "thumb_url": row.get("thumb_url") or thumb_url(row["video_id"]),
        "tags": tags,
        "watch_url": watch_url(row["video_id"]),
        "is_music_topic": is_music_topic_channel(channel_title),
        "is_unavailable": is_unavailable_video(title),
    }
    if extra:
        out.update(extra)
    return out
