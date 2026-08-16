"""Background classify-after-share + FCM notify (does not block HTTP save)."""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, Optional

from backend import db, organize, push, youtube as yt

log = logging.getLogger("clip_queue.share_classify")


def enqueue_after_save(
    user_id: int,
    video_id: str,
    *,
    source: str,
    title: str = "",
    channel_title: str = "",
    thumb_url: str = "",
    duration_sec: Optional[int] = None,
    description: str = "",
) -> None:
    t = threading.Thread(
        target=_run,
        kwargs={
            "user_id": user_id,
            "video_id": video_id,
            "source": source,
            "title": title or "",
            "channel_title": channel_title or "",
            "thumb_url": thumb_url or "",
            "duration_sec": duration_sec,
            "description": description or "",
        },
        name=f"share-classify-{video_id[:8]}",
        daemon=True,
    )
    t.start()


def _lists_for_video(uid: int, video_id: str) -> list[dict]:
    rows = db.fetchall(
        """
        SELECT l.id, l.title
        FROM list_items x
        JOIN lists l ON l.id = x.list_id
        WHERE x.video_id = ? AND l.user_id = ?
        ORDER BY l.title
        """,
        (video_id, uid),
    )
    return [{"id": r["id"], "title": r.get("title") or ""} for r in rows]


def _tags_for_video(uid: int, video_id: str) -> list[dict]:
    return db.fetchall(
        """
        SELECT t.id, t.name, t.emoji, t.color
        FROM item_tags it
        JOIN user_tags t ON t.id = it.tag_id
        WHERE it.user_id = ? AND it.video_id = ?
        """,
        (uid, video_id),
    )


def _record_save_event(
    uid: int,
    video_id: str,
    *,
    source: str,
    title: str,
    channel_title: str,
    thumb_url: str,
    classified_into: list,
    tags: list,
    lists: list,
    classify_engine: str,
    classify_reason: str,
) -> None:
    db.execute(
        """
        INSERT INTO save_events (
          user_id, video_id, source, title, channel_title, thumb_url,
          classified_json, tags_json, lists_json, classify_engine, classify_reason
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            uid,
            video_id,
            (source or "")[:40],
            (title or "")[:300],
            (channel_title or "")[:200],
            (thumb_url or "")[:500],
            json.dumps(classified_into, ensure_ascii=False),
            json.dumps(tags, ensure_ascii=False),
            json.dumps(lists, ensure_ascii=False),
            (classify_engine or "")[:40],
            (classify_reason or "")[:300],
        ),
    )


def _push_copy(title: str, folder_titles: list[str]) -> tuple[str, str]:
    """Notification title = video name; body = folder it landed in."""
    short = (title or "Видео").strip() or "Видео"
    if len(short) > 80:
        short = short[:77] + "…"
    if folder_titles:
        folders = ", ".join(folder_titles[:3])
        return short, f"→ {folders}"
    return short, "Сохранено в очередь"


def _run(
    *,
    user_id: int,
    video_id: str,
    source: str,
    title: str,
    channel_title: str,
    thumb_url: str,
    duration_sec: Optional[int],
    description: str,
) -> None:
    try:
        classify_meta: dict[str, Any] = organize.classify_new_video(
            user_id,
            video_id,
            title=title or None,
            channel_title=channel_title or None,
            duration_sec=duration_sec,
            description=description or None,
        )
        matched = classify_meta.get("matched") or []
        classified_into = [
            {"list_id": m.get("list_id"), "list_title": m.get("list_title")}
            for m in matched
        ]
        folder_titles = [
            str(m.get("list_title")).strip()
            for m in matched
            if (m.get("list_title") or "").strip()
        ]
        # de-dupe preserve order
        seen: set[str] = set()
        unique_folders: list[str] = []
        for f in folder_titles:
            key = f.lower()
            if key in seen:
                continue
            seen.add(key)
            unique_folders.append(f)

        in_lists = _lists_for_video(user_id, video_id)
        tags = _tags_for_video(user_id, video_id)
        try:
            _record_save_event(
                user_id,
                video_id,
                source=source,
                title=title,
                channel_title=channel_title,
                thumb_url=thumb_url or yt.thumb_url(video_id),
                classified_into=classified_into,
                tags=tags,
                lists=in_lists,
                classify_engine=str(classify_meta.get("engine") or ""),
                classify_reason=str(classify_meta.get("reason") or ""),
            )
        except Exception as e:
            log.warning("async save_event failed: %s", e)

        push_title, push_body = _push_copy(title, unique_folders)
        primary_folder = unique_folders[0] if unique_folders else ""
        push.send_to_user(
            user_id,
            title=push_title,
            body=push_body,
            data={
                "type": "classified",
                "video_id": video_id,
                "list_title": primary_folder,
                "video_title": (title or "")[:200],
                "title": push_title[:120],
                "body": push_body[:400],
            },
        )
        log.info(
            "share classify done user=%s video=%s folders=%s engine=%s",
            user_id,
            video_id,
            unique_folders,
            classify_meta.get("engine"),
        )
    except Exception:
        log.exception("share classify failed user=%s video=%s", user_id, video_id)
