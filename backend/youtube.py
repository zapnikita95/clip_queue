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


def search_videos(
    query: str,
    *,
    max_results: int = 12,
    relevance_language: str = "ru",
    exclude_ids: set[str] | None = None,
    access_token: str | None = None,
    channel_id: str | None = None,
    order: str = "relevance",
) -> list[dict[str, Any]]:
    """YouTube Data API search.list.

    Prefers YOUTUBE_API_KEY; falls back to user OAuth Bearer (youtube.readonly).
    relatedToVideoId is deprecated — we search by topic / channel.
    """
    key = (os.environ.get("YOUTUBE_API_KEY") or "").strip()
    token = (access_token or "").strip()
    q = (query or "").strip()
    if not key and not token:
        return []
    if not q and not channel_id:
        return []
    exclude_ids = exclude_ids or set()
    params: dict[str, Any] = {
        "part": "snippet",
        "type": "video",
        "maxResults": min(25, max(max_results + 4, 8)),
        "relevanceLanguage": relevance_language,
        "safeSearch": "moderate",
        "order": order if order in ("relevance", "date", "viewCount", "rating") else "relevance",
    }
    if q:
        params["q"] = q[:120]
    if channel_id:
        params["channelId"] = channel_id
    headers: dict[str, str] = {}
    if key:
        params["key"] = key
    else:
        headers["Authorization"] = f"Bearer {token}"
    try:
        r = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params=params,
            headers=headers or None,
            timeout=12,
        )
    except Exception as e:
        print(f"[yt search] network: {e}", flush=True)
        return []
    if r.status_code != 200:
        print(f"[yt search] HTTP {r.status_code}: {r.text[:240]}", flush=True)
        return []
    items = (r.json() or {}).get("items") or []
    out: list[dict[str, Any]] = []
    for it in items:
        vid = ((it.get("id") or {}).get("videoId") or "").strip()
        if not vid or vid in exclude_ids:
            continue
        sn = it.get("snippet") or {}
        thumbs = sn.get("thumbnails") or {}
        thumb = ""
        for k in ("high", "medium", "default"):
            if k in thumbs and thumbs[k].get("url"):
                thumb = thumbs[k]["url"]
                break
        out.append(
            {
                "video_id": vid,
                "title": (sn.get("title") or "").strip(),
                "description": (sn.get("description") or "").strip(),
                "channel_id": (sn.get("channelId") or "").strip(),
                "channel_title": (sn.get("channelTitle") or "").strip(),
                "thumb_url": thumb or thumb_url(vid),
                "watch_url": watch_url(vid),
                "published_at": sn.get("publishedAt"),
                "duration_sec": None,
                "duration_label": "",
                "source": "youtube_search",
                "in_library": False,
            }
        )
        if len(out) >= max_results:
            break
    return out


def youtube_search_configured() -> dict[str, bool]:
    return {
        "api_key": bool((os.environ.get("YOUTUBE_API_KEY") or "").strip()),
    }


def format_duration(sec: Optional[int]) -> str:
    if sec is None or sec < 0:
        return ""
    h, rem = divmod(int(sec), 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


# YouTube Shorts are usually ≤60s; keep ≤90 so borderline clips leave the main queue.
SHORTS_MAX_SEC = 90
# Planning queue = long-form only. Sub-6min atmospheric/clips go to «Короткие».
SHORTFORM_MAX_SEC = 6 * 60
# 10h+ loops / ambient dumps are not something people schedule to watch.
MARATHON_MIN_SEC = 10 * 3600

_MUSIC_TITLE_RE = re.compile(
    r"("
    r"official\s+music\s+video"
    r"|official\s+audio"
    r"|official\s+lyric"
    r"|lyric\s*video"
    r"|lyrics?\s+video"
    r"|music\s+video"
    r"|\(official\s+video\)"
    r"|\(official\s+audio\)"
    r"|\(audio\)"
    r"|\baudio\b.*\bofficial\b"
    r"|\bvisualizer\b"
    r"|\bnightcore\b"
    r"|\bspeed\s*up\b"
    r"|\bsped\s*up\b"
    r"|\bost\b"
    r"|soundtrack"
    r"|theme\s+song"
    r")",
    re.I,
)

# "Artist - Track" / "Artist–Track" / "song-band" typical for clips.
_ARTIST_TRACK_RE = re.compile(
    r"^.+\s*[-–—]\s*.+$",
)


def is_music_topic_channel(channel_title: str | None) -> bool:
    """Legacy name: any music *channel* (Topic, VEVO, Music Library, …)."""
    return is_music_channel(channel_title)


def is_music_channel(channel_title: str | None) -> bool:
    t = (channel_title or "").strip()
    if not t:
        return False
    tl = t.lower()
    if tl.endswith(" - topic") or tl.endswith(" topic") or tl == "topic":
        return True
    if "vevo" in tl:
        return True
    if "music library" in tl:
        return True
    if "auto-generated by youtube" in tl or "autogenerated by youtube" in tl:
        return True
    if tl in ("youtube music", "release radar"):
        return True
    return False


def is_music_title(title: str | None) -> bool:
    t = (title or "").strip()
    if not t:
        return False
    if _MUSIC_TITLE_RE.search(t):
        return True
    return False


def is_music_content(
    title: str | None,
    channel_title: str | None = None,
    duration_sec: int | None = None,
) -> bool:
    """Clips / YT Music / VEVO / Topic — anything that belongs in Музыка, not Очередь."""
    if is_music_channel(channel_title):
        return True
    if is_music_title(title):
        return True
    # Artist - Song + typical clip length (and not an obvious long-form talk title)
    t = (title or "").strip()
    if t and _ARTIST_TRACK_RE.match(t) and duration_sec is not None:
        if 60 <= int(duration_sec) <= 8 * 60:
            # Avoid "Channel - Episode 12" style talk shows when title is very long
            if len(t) <= 80 and not re.search(
                r"\b(episode|выпуск|сезон|podcast|подкаст|stream|стрим|обзор|разбор)\b",
                t,
                re.I,
            ):
                return True
    return False


def _duration_sec(duration_sec: int | None) -> int | None:
    if duration_sec is None:
        return None
    try:
        sec = int(duration_sec)
    except (TypeError, ValueError):
        return None
    return sec if sec > 0 else None


def is_short(
    duration_sec: int | None,
    title: str | None = None,
    description: str | None = None,
) -> bool:
    blob = f"{title or ''} {description or ''}".lower()
    if "#shorts" in blob or "#short" in blob or "/shorts/" in blob:
        return True
    sec = _duration_sec(duration_sec)
    return sec is not None and sec <= SHORTS_MAX_SEC


def is_shortform(
    duration_sec: int | None,
    title: str | None = None,
    description: str | None = None,
) -> bool:
    """Anything shorter than a real watch session (≤6 min), including Shorts."""
    if is_short(duration_sec, title=title, description=description):
        return True
    sec = _duration_sec(duration_sec)
    return sec is not None and sec <= SHORTFORM_MAX_SEC


def is_marathon(duration_sec: int | None) -> bool:
    sec = _duration_sec(duration_sec)
    return sec is not None and sec >= MARATHON_MIN_SEC


def content_bucket(
    title: str | None,
    channel_title: str | None = None,
    duration_sec: int | None = None,
    description: str | None = None,
) -> str:
    """Return: unavailable | music | shorts | shortform | marathon | video."""
    if is_unavailable_video(title):
        return "unavailable"
    if is_music_content(title, channel_title, duration_sec):
        return "music"
    # Classic Shorts first (own tab), then the rest of ≤6min junk.
    if is_short(duration_sec, title=title, description=description):
        return "shorts"
    if is_marathon(duration_sec):
        return "marathon"
    if is_shortform(duration_sec, title=title, description=description):
        return "shortform"
    return "video"


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
    duration_sec = row.get("duration_sec")
    bucket = content_bucket(title, channel_title, duration_sec, row.get("description"))
    out = {
        "video_id": row["video_id"],
        "title": title,
        "description": row.get("description") or "",
        "channel_id": row.get("channel_id") or "",
        "channel_title": channel_title,
        "duration_sec": duration_sec,
        "duration_label": format_duration(duration_sec),
        "published_at": row.get("published_at"),
        "thumb_url": row.get("thumb_url") or thumb_url(row["video_id"]),
        "tags": tags,
        "watch_url": watch_url(row["video_id"]),
        "is_music_topic": bucket == "music",
        "is_music": bucket == "music",
        "is_short": bucket in ("shorts", "shortform"),
        "is_shortform": bucket in ("shorts", "shortform"),
        "is_marathon": bucket == "marathon",
        "content_kind": bucket,
        "is_unavailable": bucket == "unavailable",
    }
    if extra:
        out.update(extra)
    return out
