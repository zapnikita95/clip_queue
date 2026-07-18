"""Clip Queue Flask app — separate Railway service from Movie Planner."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, g, jsonify, redirect, request, send_from_directory

from backend import auth, db, google_oauth, llm, organize, sync_jobs, takeout, yt_sync
from backend import similarity as sim
from backend import youtube as yt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("clip_queue")

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"


def create_app() -> Flask:
    load_dotenv(ROOT / ".env")
    app = Flask(__name__, static_folder=None)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or "dev-clip-queue"
    db.init_db()

    def json_error(msg: str, status: int = 400):
        return jsonify({"ok": False, "error": msg}), status

    def current_user():
        return getattr(g, "user", None)

    def require_auth(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            header = request.headers.get("Authorization") or ""
            token = header
            if not token:
                token = request.cookies.get("cq_session") or ""
            user = auth.resolve_session(token)
            if not user:
                return json_error("Нужен вход", 401)
            g.user = user
            return fn(*args, **kwargs)

        return wrapper

    @app.get("/health")
    def health():
        return jsonify(
            {
                "ok": True,
                "service": "clip_queue",
                "version": "0.2.0",
                "db": "postgres" if db.is_postgres() else "sqlite",
                "google_oauth": google_oauth.configured(),
                "llm": llm.available(),
            }
        )

    # ----- Auth -----

    @app.post("/api/auth/magic-link")
    def magic_link():
        body = request.get_json(silent=True) or {}
        email = auth.normalize_email(body.get("email") or "")
        if not email or "@" not in email:
            return json_error("Укажи email")
        code = auth.create_magic_code(email)
        # No email provider in MVP — return hint; in DEV also echo code
        payload = {
            "ok": True,
            "email": email,
            "message": "Код отправлен (в MVP смотри логи сервера / ответ в DEV_LOGIN).",
        }
        if auth.dev_login_enabled():
            payload["dev_code"] = code
        app.logger.info("magic_code email=%s code=%s", email, code)
        print(f"[clip_queue] magic code for {email}: {code}", flush=True)
        return jsonify(payload)

    @app.post("/api/auth/verify")
    def verify():
        body = request.get_json(silent=True) or {}
        try:
            session = auth.verify_magic_code(
                body.get("email") or "", body.get("code") or ""
            )
        except ValueError as e:
            return json_error(str(e), 400)
        return jsonify({"ok": True, **session})

    @app.post("/api/auth/dev-login")
    def dev_login():
        if not auth.dev_login_enabled():
            return json_error("DEV_LOGIN выключен", 403)
        user = auth.ensure_dev_user()
        session = auth.create_session(int(user["id"]))
        return jsonify({"ok": True, **session})

    @app.get("/api/me")
    @require_auth
    def me():
        u = current_user()
        uid = u["user_id"]
        lib = db.fetchone(
            "SELECT COUNT(*) AS c FROM library_items WHERE user_id = ?",
            (uid,),
        )
        last_sync = db.fetchone(
            "SELECT status, stats_json, created_at FROM sync_runs "
            "WHERE user_id = ? AND kind = 'youtube_oauth' ORDER BY id DESC LIMIT 1",
            (uid,),
        )
        stats = {}
        if last_sync and last_sync.get("stats_json"):
            try:
                stats = json.loads(last_sync["stats_json"])
            except Exception:
                stats = {}
        return jsonify(
            {
                "ok": True,
                "user": {
                    "id": uid,
                    "email": u["email"],
                    "name": u["name"],
                },
                "google_oauth_configured": google_oauth.configured(),
                "youtube_connected": google_oauth.youtube_connected(uid),
                "library_count": int((lib or {}).get("c") or 0),
                "last_youtube_sync": {
                    "status": (last_sync or {}).get("status"),
                    "at": str((last_sync or {}).get("created_at") or "") or None,
                    "stats": stats,
                }
                if last_sync
                else None,
            }
        )

    @app.post("/api/auth/logout")
    @require_auth
    def logout():
        auth.destroy_session(current_user()["token"])
        return jsonify({"ok": True})

    @app.get("/api/auth/google/status")
    def google_status():
        return jsonify(
            {
                "ok": True,
                "configured": google_oauth.configured(),
                "redirect_uri": google_oauth.redirect_uri() if google_oauth.configured() else None,
            }
        )

    @app.get("/api/auth/google/start")
    def google_start():
        try:
            url = google_oauth.start_url()
        except Exception as e:
            return json_error(str(e), 503)
        return redirect(url)

    @app.get("/api/auth/google/callback")
    def google_callback():
        err = request.args.get("error")
        if err:
            return redirect(f"/login?error={err}")
        code = request.args.get("code") or ""
        state = request.args.get("state") or ""
        try:
            session = google_oauth.login_with_code(code, state)
        except Exception as e:
            return redirect(f"/login?error={str(e)[:120]}")
        # SPA picks token and immediately streams YouTube sync
        return redirect(f"/auth/callback?token={session['token']}&autosync=1")

    @app.post("/api/youtube/sync")
    @require_auth
    def youtube_sync():
        """Start background sync (avoids Railway proxy 502 on long streams)."""
        uid = current_user()["user_id"]
        if (request.args.get("plain") or "").strip() == "1":
            try:
                log.info("plain sync start user=%s", uid)
                stats = yt_sync.sync_youtube_library(uid)
                log.info("plain sync done user=%s", uid)
            except Exception as e:
                log.exception("plain sync failed user=%s", uid)
                return json_error(str(e), 502)
            return jsonify({"ok": True, "stats": stats})

        job = sync_jobs.start_youtube_sync(uid)
        log.info("sync job started user=%s job=%s", uid, job.get("id"))
        return jsonify({"ok": True, "job": job})

    @app.get("/api/youtube/sync/status")
    @require_auth
    def youtube_sync_status():
        uid = current_user()["user_id"]
        job_id = (request.args.get("job_id") or "").strip()
        job = sync_jobs.get_job(job_id) if job_id else sync_jobs.active_job_for_user(uid)
        if not job or job.get("user_id") != uid:
            return json_error("Нет задачи синка", 404)
        return jsonify({"ok": True, "job": job})

    @app.post("/api/youtube/takeout")
    @require_auth
    def youtube_takeout():
        uid = current_user()["user_id"]
        body = request.get_json(silent=True)
        if body is None:
            return json_error("Нужен JSON тела (watch-history)")
        try:
            stats = takeout.import_watch_history(uid, body)
        except ValueError as e:
            return json_error(str(e), 400)
        except Exception as e:
            return json_error(str(e), 500)
        return jsonify({"ok": True, "stats": stats})

    @app.post("/api/organize/propose")
    @require_auth
    def organize_propose():
        uid = current_user()["user_id"]
        body = request.get_json(silent=True) or {}
        use_llm = bool(body.get("use_llm")) or (request.args.get("llm") == "1")
        proposal = organize.propose_structure(uid, use_llm=use_llm)
        return jsonify({"ok": True, "proposal": proposal})

    @app.get("/api/organize/rules")
    @require_auth
    def organize_rules():
        uid = current_user()["user_id"]
        return jsonify({"ok": True, "rules": organize.list_rules(uid)})

    @app.post("/api/organize/preview-classify")
    @require_auth
    def organize_preview_classify():
        """Dry-run: where would this video go under saved rules."""
        uid = current_user()["user_id"]
        body = request.get_json(silent=True) or {}
        matched = organize.match_rules_for_video(
            uid,
            title=body.get("title"),
            channel_title=body.get("channel_title"),
            duration_sec=body.get("duration_sec"),
        )
        return jsonify(
            {
                "ok": True,
                "matched": [
                    {"list_id": m["list_id"], "list_title": m.get("list_title")}
                    for m in matched
                ],
            }
        )

    @app.post("/api/organize/apply")
    @require_auth
    def organize_apply():
        uid = current_user()["user_id"]
        body = request.get_json(silent=True) or {}
        proposal = body.get("proposal")
        if not proposal and body.get("proposal_id"):
            row = db.fetchone(
                "SELECT * FROM organize_proposals WHERE id = ? AND user_id = ?",
                (int(body["proposal_id"]), uid),
            )
            if not row:
                return json_error("Предложение не найдено", 404)
            proposal = json.loads(row["proposal_json"])
        if not proposal:
            return json_error("Нужен proposal")
        result = organize.apply_proposal(uid, proposal)
        if body.get("proposal_id"):
            db.execute(
                "UPDATE organize_proposals SET applied = 1 WHERE id = ? AND user_id = ?",
                (int(body["proposal_id"]), uid),
            )
        return jsonify(result)

    # ----- Videos -----

    def upsert_video(meta: dict) -> None:
        tags_json = json.dumps(meta.get("tags") or [], ensure_ascii=False)
        if db.is_postgres():
            db.execute(
                """
                INSERT INTO videos (
                  video_id, title, description, channel_id, channel_title,
                  duration_sec, published_at, thumb_url, tags_json, fetched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NOW())
                ON CONFLICT (video_id) DO UPDATE SET
                  title = EXCLUDED.title,
                  description = EXCLUDED.description,
                  channel_id = EXCLUDED.channel_id,
                  channel_title = EXCLUDED.channel_title,
                  duration_sec = COALESCE(EXCLUDED.duration_sec, videos.duration_sec),
                  published_at = COALESCE(EXCLUDED.published_at, videos.published_at),
                  thumb_url = EXCLUDED.thumb_url,
                  tags_json = EXCLUDED.tags_json,
                  fetched_at = NOW()
                """,
                (
                    meta["video_id"],
                    meta.get("title") or "",
                    meta.get("description") or "",
                    meta.get("channel_id") or "",
                    meta.get("channel_title") or "",
                    meta.get("duration_sec"),
                    meta.get("published_at"),
                    meta.get("thumb_url") or "",
                    tags_json,
                ),
            )
        else:
            db.execute(
                """
                INSERT INTO videos (
                  video_id, title, description, channel_id, channel_title,
                  duration_sec, published_at, thumb_url, tags_json, fetched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(video_id) DO UPDATE SET
                  title = excluded.title,
                  description = excluded.description,
                  channel_id = excluded.channel_id,
                  channel_title = excluded.channel_title,
                  duration_sec = COALESCE(excluded.duration_sec, videos.duration_sec),
                  published_at = COALESCE(excluded.published_at, videos.published_at),
                  thumb_url = excluded.thumb_url,
                  tags_json = excluded.tags_json,
                  fetched_at = datetime('now')
                """,
                (
                    meta["video_id"],
                    meta.get("title") or "",
                    meta.get("description") or "",
                    meta.get("channel_id") or "",
                    meta.get("channel_title") or "",
                    meta.get("duration_sec"),
                    meta.get("published_at"),
                    meta.get("thumb_url") or "",
                    tags_json,
                ),
            )

    @app.post("/api/videos/resolve")
    @require_auth
    def resolve_video():
        body = request.get_json(silent=True) or {}
        url = body.get("url") or body.get("video_id") or ""
        try:
            meta = yt.resolve(url)
        except ValueError as e:
            return json_error(str(e), 400)
        except Exception as e:
            return json_error(f"Не удалось получить метаданные: {e}", 502)
        return jsonify({"ok": True, "video": meta})

    @app.post("/api/videos/save")
    @require_auth
    def save_video():
        body = request.get_json(silent=True) or {}
        url = body.get("url") or body.get("video_id") or ""
        source = (body.get("source") or "paste").strip()[:40]
        note = (body.get("note") or "").strip()[:2000]
        status = (body.get("status") or "queue").strip()
        if status not in ("queue", "in_progress", "watched", "archived"):
            status = "queue"
        try:
            meta = yt.resolve(url)
        except ValueError as e:
            return json_error(str(e), 400)
        except Exception as e:
            return json_error(f"Не удалось получить метаданные: {e}", 502)

        upsert_video(meta)
        uid = current_user()["user_id"]
        vid = meta["video_id"]

        existing = db.fetchone(
            "SELECT * FROM library_items WHERE user_id = ? AND video_id = ?",
            (uid, vid),
        )
        if existing:
            db.execute(
                "UPDATE library_items SET status = ?, note = ?, source = ? "
                "WHERE user_id = ? AND video_id = ?",
                (status, note or existing.get("note") or "", source, uid, vid),
            )
        else:
            db.execute(
                "INSERT INTO library_items (user_id, video_id, status, note, source) "
                "VALUES (?, ?, ?, ?, ?)",
                (uid, vid, status, note, source),
            )

        list_id = body.get("list_id")
        if list_id:
            _add_to_list(uid, int(list_id), vid)

        tags = body.get("tags") or []
        if isinstance(tags, list):
            for t in tags:
                name = str(t).strip()
                if name:
                    _ensure_tag_on_item(uid, vid, name)

        # Apply saved classification from last «Разложить → ОК»
        apply_class = body.get("apply_classification")
        if apply_class is None:
            apply_class = True
        matched = []
        if apply_class:
            matched = organize.apply_rules_to_video(
                uid,
                vid,
                title=meta.get("title"),
                channel_title=meta.get("channel_title"),
                duration_sec=meta.get("duration_sec"),
            )

        item = _library_card(uid, vid)
        return jsonify(
            {
                "ok": True,
                "item": item,
                "classified_into": [
                    {"list_id": m["list_id"], "list_title": m.get("list_title")}
                    for m in matched
                ],
            }
        )

    def _library_card(uid: int, video_id: str) -> dict | None:
        row = db.fetchone(
            """
            SELECT v.*, li.status, li.note, li.source, li.saved_at, li.watched_at
            FROM library_items li
            JOIN videos v ON v.video_id = li.video_id
            WHERE li.user_id = ? AND li.video_id = ?
            """,
            (uid, video_id),
        )
        if not row:
            return None
        tags = db.fetchall(
            """
            SELECT t.id, t.name, t.emoji, t.color
            FROM item_tags it
            JOIN user_tags t ON t.id = it.tag_id
            WHERE it.user_id = ? AND it.video_id = ?
            """,
            (uid, video_id),
        )
        return yt.card_from_video_row(
            row,
            {
                "status": row.get("status"),
                "note": row.get("note") or "",
                "source": row.get("source"),
                "saved_at": str(row.get("saved_at") or ""),
                "watched_at": str(row.get("watched_at") or "") or None,
                "user_tags": tags,
            },
        )

    def _ensure_tag_on_item(uid: int, video_id: str, name: str, emoji: str = "") -> dict:
        name = (name or "").strip()[:60]
        if not name:
            raise ValueError("Пустой тег")
        tag = db.fetchone(
            "SELECT * FROM user_tags WHERE user_id = ? AND name = ?",
            (uid, name),
        )
        if not tag:
            if db.is_postgres():
                with db.connect() as conn:
                    cur = conn.execute(
                        "INSERT INTO user_tags (user_id, name, emoji) VALUES (%s, %s, %s) RETURNING id, name, emoji, color",
                        (uid, name, (emoji or "")[:8]),
                    )
                    tag = dict(cur.fetchone())
            else:
                db.execute(
                    "INSERT INTO user_tags (user_id, name, emoji) VALUES (?, ?, ?)",
                    (uid, name, (emoji or "")[:8]),
                )
                tag = db.fetchone(
                    "SELECT * FROM user_tags WHERE user_id = ? AND name = ?",
                    (uid, name),
                )
        tag_id = int(tag["id"])
        db.execute(
            "INSERT INTO item_tags (user_id, video_id, tag_id) VALUES (?, ?, ?) "
            + (
                "ON CONFLICT DO NOTHING"
                if db.is_postgres()
                else "ON CONFLICT(user_id, video_id, tag_id) DO NOTHING"
            ),
            (uid, video_id, tag_id),
        )
        return {
            "id": tag_id,
            "name": tag.get("name") or name,
            "emoji": tag.get("emoji") or "",
            "color": tag.get("color") or "#ff3b30",
        }

    def _add_to_list(uid: int, list_id: int, video_id: str) -> None:
        lst = db.fetchone(
            "SELECT * FROM lists WHERE id = ? AND user_id = ?",
            (list_id, uid),
        )
        if not lst:
            return
        db.execute(
            "INSERT INTO list_items (list_id, video_id, position) VALUES (?, ?, 0) "
            + (
                "ON CONFLICT DO NOTHING"
                if db.is_postgres()
                else "ON CONFLICT(list_id, video_id) DO NOTHING"
            ),
            (list_id, video_id),
        )

    @app.get("/api/library")
    @require_auth
    def library():
        uid = current_user()["user_id"]
        status = (request.args.get("status") or "queue").strip()
        q = (request.args.get("q") or "").strip().lower()
        # video = long-form only (6min–10h). Junk buckets: music | shorts | shortform | marathon
        kind = (request.args.get("kind") or "video").strip().lower()
        channel = (request.args.get("channel") or "").strip()
        limit = min(int(request.args.get("limit") or 60), 200)
        offset = max(int(request.args.get("offset") or 0), 0)
        # Over-fetch then filter — junk buckets otherwise fill the page
        fetch_n = min(3000, max(limit * 30, 300))
        rows = db.fetchall(
            """
            SELECT v.*, li.status, li.note, li.source, li.saved_at, li.watched_at
            FROM library_items li
            JOIN videos v ON v.video_id = li.video_id
            WHERE li.user_id = ? AND li.status = ?
            ORDER BY li.saved_at DESC
            LIMIT ?
            """,
            (uid, status, fetch_n),
        )
        items = []
        for row in rows:
            bucket = yt.content_bucket(
                row.get("title"),
                row.get("channel_title"),
                row.get("duration_sec"),
                row.get("description"),
            )
            if bucket == "unavailable":
                continue
            if kind == "video" and bucket != "video":
                continue
            if kind == "music" and bucket != "music":
                continue
            if kind == "shorts" and bucket != "shorts":
                continue
            if kind in ("shortform", "short") and bucket not in ("shorts", "shortform"):
                continue
            if kind == "marathon" and bucket != "marathon":
                continue
            if channel and (row.get("channel_title") or "").strip() != channel:
                continue
            if q:
                blob = f"{row.get('title') or ''} {row.get('channel_title') or ''}".lower()
                if q not in blob:
                    continue
            tags = db.fetchall(
                """
                SELECT t.id, t.name, t.emoji, t.color
                FROM item_tags it
                JOIN user_tags t ON t.id = it.tag_id
                WHERE it.user_id = ? AND it.video_id = ?
                """,
                (uid, row["video_id"]),
            )
            card = yt.card_from_video_row(
                row,
                {
                    "status": row.get("status"),
                    "note": row.get("note") or "",
                    "source": row.get("source"),
                    "saved_at": str(row.get("saved_at") or ""),
                    "watched_at": str(row.get("watched_at") or "") or None,
                    "user_tags": tags,
                },
            )
            items.append(card)
            if len(items) >= offset + limit:
                break
        page = items[offset : offset + limit]
        return jsonify({"ok": True, "items": page, "kind": kind, "channel": channel or None})

    @app.get("/api/channels")
    @require_auth
    def channels():
        """Browseable channel list from the user's library (videos, not Topic music)."""
        uid = current_user()["user_id"]
        kind = (request.args.get("kind") or "video").strip().lower()
        status = (request.args.get("status") or "queue").strip()
        rows = db.fetchall(
            """
            SELECT COALESCE(v.channel_id, '') AS channel_id,
                   COALESCE(v.channel_title, '') AS channel_title,
                   COUNT(*) AS c
            FROM library_items li
            JOIN videos v ON v.video_id = li.video_id
            WHERE li.user_id = ? AND li.status = ?
            GROUP BY COALESCE(v.channel_id, ''), COALESCE(v.channel_title, '')
            ORDER BY c DESC
            """,
            (uid, status),
        )
        out = []
        for r in rows:
            title = r.get("channel_title") or "Без канала"
            if yt.is_unavailable_video(title):
                continue
            is_music = yt.is_music_channel(title)
            if kind == "video" and is_music:
                continue
            if kind == "music" and not is_music:
                continue
            # shorts: keep all non-music channels (short clips live under video channels too)
            if kind == "shorts" and is_music:
                continue
            out.append(
                {
                    "channel_id": r.get("channel_id") or "",
                    "channel_title": title,
                    "count": int(r.get("c") or 0),
                    "is_music_topic": is_music,
                    "is_music": is_music,
                }
            )
        return jsonify({"ok": True, "channels": out, "kind": kind})

    @app.patch("/api/library/<video_id>")
    @require_auth
    def patch_library(video_id: str):
        uid = current_user()["user_id"]
        body = request.get_json(silent=True) or {}
        row = db.fetchone(
            "SELECT * FROM library_items WHERE user_id = ? AND video_id = ?",
            (uid, video_id),
        )
        if not row:
            return json_error("Нет в библиотеке", 404)
        status = body.get("status")
        note = body.get("note")
        sets = []
        params: list = []
        if status in ("queue", "in_progress", "watched", "archived"):
            sets.append("status = ?")
            params.append(status)
            if status == "watched":
                sets.append(
                    "watched_at = NOW()"
                    if db.is_postgres()
                    else "watched_at = datetime('now')"
                )
                db.execute(
                    "INSERT INTO watch_events (user_id, video_id, event_type) VALUES (?, ?, ?)",
                    (uid, video_id, "mark_watched"),
                )
            elif status == "in_progress":
                db.execute(
                    "INSERT INTO watch_events (user_id, video_id, event_type) VALUES (?, ?, ?)",
                    (uid, video_id, "mark_started"),
                )
        if note is not None:
            sets.append("note = ?")
            params.append(str(note)[:2000])
        if not sets:
            return json_error("Нечего менять")
        # mixed SQL with NOW() already inlined — only append params for ?
        sql = "UPDATE library_items SET " + ", ".join(sets) + " WHERE user_id = ? AND video_id = ?"
        params.extend([uid, video_id])
        db.execute(sql, params)
        return jsonify({"ok": True, "item": _library_card(uid, video_id)})

    @app.delete("/api/library/<video_id>")
    @require_auth
    def delete_library(video_id: str):
        uid = current_user()["user_id"]
        db.execute(
            "DELETE FROM library_items WHERE user_id = ? AND video_id = ?",
            (uid, video_id),
        )
        db.execute(
            "DELETE FROM item_tags WHERE user_id = ? AND video_id = ?",
            (uid, video_id),
        )
        return jsonify({"ok": True})

    @app.post("/api/videos/<video_id>/open")
    @require_auth
    def open_video(video_id: str):
        """Open on YouTube = started (leaves main queue until marked watched / back)."""
        uid = current_user()["user_id"]
        db.execute(
            "INSERT INTO watch_events (user_id, video_id, event_type) VALUES (?, ?, ?)",
            (uid, video_id, "open_yt"),
        )
        row = db.fetchone(
            "SELECT status FROM library_items WHERE user_id = ? AND video_id = ?",
            (uid, video_id),
        )
        moved = False
        if row and (row.get("status") or "") == "queue":
            db.execute(
                "UPDATE library_items SET status = 'in_progress' "
                "WHERE user_id = ? AND video_id = ?",
                (uid, video_id),
            )
            db.execute(
                "INSERT INTO watch_events (user_id, video_id, event_type) VALUES (?, ?, ?)",
                (uid, video_id, "mark_started"),
            )
            moved = True
        return jsonify(
            {
                "ok": True,
                "watch_url": yt.watch_url(video_id),
                "status": "in_progress" if moved else (row or {}).get("status"),
                "moved_to_started": moved,
            }
        )

    @app.get("/api/videos/<video_id>")
    @require_auth
    def get_video(video_id: str):
        uid = current_user()["user_id"]
        item = _library_card(uid, video_id)
        if not item:
            row = db.fetchone("SELECT * FROM videos WHERE video_id = ?", (video_id,))
            if not row:
                return json_error("Не найдено", 404)
            item = yt.card_from_video_row(row)
        return jsonify({"ok": True, "item": item})

    @app.get("/api/videos/<video_id>/similar")
    @require_auth
    def similar(video_id: str):
        uid = current_user()["user_id"]
        anchor_row = db.fetchone("SELECT * FROM videos WHERE video_id = ?", (video_id,))
        if not anchor_row:
            return json_error("Нет видео", 404)
        anchor = yt.card_from_video_row(anchor_row)
        anchor["tags"] = sim.parse_tags_json(anchor_row.get("tags_json"))

        rows = db.fetchall(
            """
            SELECT v.* FROM library_items li
            JOIN videos v ON v.video_id = li.video_id
            WHERE li.user_id = ? AND li.video_id != ?
            """,
            (uid, video_id),
        )
        candidates = []
        for r in rows:
            c = yt.card_from_video_row(r)
            c["tags"] = sim.parse_tags_json(r.get("tags_json"))
            candidates.append(c)

        anchor_tag_ids = {
            r["tag_id"]
            for r in db.fetchall(
                "SELECT tag_id FROM item_tags WHERE user_id = ? AND video_id = ?",
                (uid, video_id),
            )
        }
        # rebuild overlap counts
        from collections import defaultdict

        vid_tags: dict[str, set] = defaultdict(set)
        for r in db.fetchall(
            "SELECT video_id, tag_id FROM item_tags WHERE user_id = ?", (uid,)
        ):
            vid_tags[r["video_id"]].add(r["tag_id"])
        overlap = {
            vid: len(tags & anchor_tag_ids)
            for vid, tags in vid_tags.items()
            if vid != video_id
        }

        ranked = sim.rank_similar(anchor, candidates, tag_overlap=overlap, limit=16)
        return jsonify({"ok": True, "items": ranked})

    # ----- Home -----

    @app.get("/api/home/shell")
    @require_auth
    def home_shell():
        uid = current_user()["user_id"]
        queue_n = db.fetchone(
            "SELECT COUNT(*) AS c FROM library_items WHERE user_id = ? AND status = 'queue'",
            (uid,),
        )
        started_n = db.fetchone(
            "SELECT COUNT(*) AS c FROM library_items WHERE user_id = ? AND status = 'in_progress'",
            (uid,),
        )
        watched_n = db.fetchone(
            "SELECT COUNT(*) AS c FROM library_items WHERE user_id = ? AND status = 'watched'",
            (uid,),
        )
        lists_n = db.fetchone(
            "SELECT COUNT(*) AS c FROM lists WHERE user_id = ?",
            (uid,),
        )
        return jsonify(
            {
                "ok": True,
                "counts": {
                    "queue": int((queue_n or {}).get("c") or 0),
                    "started": int((started_n or {}).get("c") or 0),
                    "watched": int((watched_n or {}).get("c") or 0),
                    "lists": int((lists_n or {}).get("c") or 0),
                },
                "rails": [
                    {"id": "queue", "title": "Видео в очереди"},
                    {"id": "started", "title": "Начатые"},
                    {"id": "watched", "title": "Просмотренные"},
                    {"id": "from_playlists", "title": "Из твоих плейлистов"},
                    {"id": "channels_you_watch", "title": "По каналам"},
                    {"id": "by_duration", "title": "Под сейчас"},
                    {"id": "continue_vibe", "title": "В том же вайбе"},
                    {"id": "music_topic", "title": "Музыка (отдельно)"},
                    {"id": "shortform", "title": "До 6 минут (шлак)"},
                    {"id": "marathon", "title": "10+ часов"},
                    {"id": "for_this_hour", "title": "Обычно в это время"},
                ],
            }
        )

    def _clean_lib_rows(
        rows: list[dict],
        *,
        allow_music: bool = False,
        allow_shorts: bool = False,
        allow_shortform: bool = False,
        allow_marathon: bool = False,
    ) -> list[dict]:
        out = []
        for row in rows:
            bucket = yt.content_bucket(
                row.get("title"),
                row.get("channel_title"),
                row.get("duration_sec"),
                row.get("description"),
            )
            if bucket == "unavailable":
                continue
            if bucket == "music" and not allow_music:
                continue
            if bucket == "shorts" and not (allow_shorts or allow_shortform):
                continue
            if bucket == "shortform" and not allow_shortform:
                continue
            if bucket == "marathon" and not allow_marathon:
                continue
            out.append(row)
        return out

    def _diversify_lib_rows(
        rows: list[dict],
        limit: int,
        *,
        max_per_channel: int = 2,
    ) -> list[dict]:
        if not rows:
            return []
        out: list[dict] = []
        per_ch: dict[str, int] = {}
        deferred: list[dict] = []

        def take(row: dict, force: bool = False) -> bool:
            ch = (row.get("channel_title") or "").strip() or "?"
            if not force and per_ch.get(ch, 0) >= max_per_channel:
                return False
            per_ch[ch] = per_ch.get(ch, 0) + 1
            out.append(row)
            return True

        for row in rows:
            if len(out) >= limit:
                break
            if not take(row):
                deferred.append(row)
        for row in deferred:
            if len(out) >= limit:
                break
            take(row, force=True)
        return out[:limit]

    def _cards_from_lib_rows(rows: list[dict]) -> list[dict]:
        return [
            yt.card_from_video_row(
                r,
                {
                    "status": r.get("status"),
                    "saved_at": str(r.get("saved_at") or ""),
                    "watched_at": str(r.get("watched_at") or "") or None,
                },
            )
            for r in rows
        ]

    @app.get("/api/home/rails/<rail_id>")
    @require_auth
    def home_rail(rail_id: str):
        uid = current_user()["user_id"]
        limit = min(int(request.args.get("limit") or 18), 48)
        offset = max(int(request.args.get("offset") or 0), 0)

        if rail_id == "queue":
            pool = db.fetchall(
                """
                SELECT v.*, li.status, li.saved_at, li.watched_at, li.source
                FROM library_items li JOIN videos v ON v.video_id = li.video_id
                WHERE li.user_id = ? AND li.status = 'queue'
                ORDER BY li.saved_at DESC LIMIT ?
                """,
                (uid, max(limit * 16, 200)),
            )
            pool = _clean_lib_rows(pool, allow_music=False)
            rows = _diversify_lib_rows(pool, limit) if offset == 0 else pool[offset : offset + limit]
            return jsonify({"ok": True, "rail": rail_id, "items": _cards_from_lib_rows(rows)})

        if rail_id == "started":
            rows = db.fetchall(
                """
                SELECT v.*, li.status, li.saved_at, li.watched_at, li.source
                FROM library_items li JOIN videos v ON v.video_id = li.video_id
                WHERE li.user_id = ? AND li.status = 'in_progress'
                ORDER BY li.saved_at DESC LIMIT ? OFFSET ?
                """,
                (uid, limit, offset),
            )
            rows = _clean_lib_rows(rows, allow_music=True, allow_shorts=True)
            return jsonify({"ok": True, "rail": rail_id, "items": _cards_from_lib_rows(rows)})

        if rail_id == "watched":
            rows = db.fetchall(
                """
                SELECT v.*, li.status, li.saved_at, li.watched_at, li.source
                FROM library_items li JOIN videos v ON v.video_id = li.video_id
                WHERE li.user_id = ? AND li.status = 'watched'
                ORDER BY COALESCE(li.watched_at, li.saved_at) DESC LIMIT ? OFFSET ?
                """,
                (uid, limit, offset),
            )
            return jsonify({"ok": True, "rail": rail_id, "items": _cards_from_lib_rows(rows)})

        if rail_id in ("music_topic", "music"):
            pool = db.fetchall(
                """
                SELECT v.*, li.status, li.saved_at, li.watched_at, li.source
                FROM library_items li JOIN videos v ON v.video_id = li.video_id
                WHERE li.user_id = ? AND li.status = 'queue'
                ORDER BY li.saved_at DESC LIMIT ?
                """,
                (uid, max(limit * 16, 200)),
            )
            rows = [
                r
                for r in pool
                if yt.content_bucket(
                    r.get("title"),
                    r.get("channel_title"),
                    r.get("duration_sec"),
                    r.get("description"),
                )
                == "music"
            ]
            rows = _diversify_lib_rows(rows, limit, max_per_channel=3)
            return jsonify({"ok": True, "rail": rail_id, "items": _cards_from_lib_rows(rows)})

        if rail_id in ("shorts", "shortform"):
            pool = db.fetchall(
                """
                SELECT v.*, li.status, li.saved_at, li.watched_at, li.source
                FROM library_items li JOIN videos v ON v.video_id = li.video_id
                WHERE li.user_id = ? AND li.status = 'queue'
                ORDER BY li.saved_at DESC LIMIT ?
                """,
                (uid, max(limit * 16, 200)),
            )
            want = {"shorts", "shortform"} if rail_id == "shortform" else {"shorts"}
            rows = [
                r
                for r in pool
                if yt.content_bucket(
                    r.get("title"),
                    r.get("channel_title"),
                    r.get("duration_sec"),
                    r.get("description"),
                )
                in want
            ]
            rows = _diversify_lib_rows(rows, limit, max_per_channel=3)
            return jsonify({"ok": True, "rail": rail_id, "items": _cards_from_lib_rows(rows)})

        if rail_id == "marathon":
            pool = db.fetchall(
                """
                SELECT v.*, li.status, li.saved_at, li.watched_at, li.source
                FROM library_items li JOIN videos v ON v.video_id = li.video_id
                WHERE li.user_id = ? AND li.status = 'queue'
                ORDER BY li.saved_at DESC LIMIT ?
                """,
                (uid, max(limit * 10, 80)),
            )
            rows = [
                r
                for r in pool
                if yt.content_bucket(
                    r.get("title"),
                    r.get("channel_title"),
                    r.get("duration_sec"),
                    r.get("description"),
                )
                == "marathon"
            ]
            rows = _diversify_lib_rows(rows, limit, max_per_channel=2)
            return jsonify({"ok": True, "rail": rail_id, "items": _cards_from_lib_rows(rows)})

        if rail_id == "from_playlists":
            rows = db.fetchall(
                """
                SELECT v.*, li.status, li.saved_at, li.watched_at, li.source
                FROM library_items li JOIN videos v ON v.video_id = li.video_id
                WHERE li.user_id = ? AND li.status = 'queue' AND li.source = 'playlist'
                ORDER BY li.saved_at DESC LIMIT ?
                """,
                (uid, max(limit * 12, 120)),
            )
            rows = _clean_lib_rows(rows, allow_music=False)
            rows = _diversify_lib_rows(rows, limit)
            return jsonify({"ok": True, "rail": rail_id, "items": _cards_from_lib_rows(rows)})

        if rail_id == "by_duration":
            hour = datetime.now().hour
            # evening → longer ok; morning/work → shorter
            if 6 <= hour < 12:
                pred = "v.duration_sec IS NOT NULL AND v.duration_sec < 600"
                title = "Короткие — на утро"
            elif 12 <= hour < 18:
                pred = "v.duration_sec IS NOT NULL AND v.duration_sec BETWEEN 300 AND 1800"
                title = "Средние — на день"
            else:
                pred = "(v.duration_sec IS NULL OR v.duration_sec >= 900)"
                title = "Подлиннее — на вечер"
            rows = db.fetchall(
                f"""
                SELECT v.*, li.status, li.saved_at, li.watched_at
                FROM library_items li JOIN videos v ON v.video_id = li.video_id
                WHERE li.user_id = ? AND li.status = 'queue' AND {pred}
                ORDER BY li.saved_at DESC LIMIT ?
                """,
                (uid, max(limit * 12, 120)),
            )
            rows = _clean_lib_rows(rows, allow_music=False, allow_shorts=False)
            rows = rows[offset : offset + limit]
            return jsonify(
                {
                    "ok": True,
                    "rail": rail_id,
                    "title": title,
                    "items": _cards_from_lib_rows(rows),
                }
            )

        if rail_id == "channels_you_watch":
            channels = db.fetchall(
                """
                SELECT v.channel_title AS channel_title, v.channel_id AS channel_id, COUNT(*) AS c
                FROM library_items li JOIN videos v ON v.video_id = li.video_id
                WHERE li.user_id = ? AND li.status = 'queue'
                  AND COALESCE(v.channel_title, '') != ''
                GROUP BY v.channel_title, v.channel_id
                ORDER BY c DESC LIMIT 40
                """,
                (uid,),
            )
            channels = [
                ch
                for ch in channels
                if not yt.is_music_channel(ch.get("channel_title"))
                and not yt.is_unavailable_video(ch.get("channel_title"))
            ][:10]
            items = []
            for ch in channels:
                vids = db.fetchall(
                    """
                    SELECT v.*, li.status, li.saved_at, li.watched_at
                    FROM library_items li JOIN videos v ON v.video_id = li.video_id
                    WHERE li.user_id = ? AND li.status = 'queue'
                      AND v.channel_title = ?
                    ORDER BY li.saved_at DESC LIMIT 8
                    """,
                    (uid, ch["channel_title"]),
                )
                vids = _clean_lib_rows(vids, allow_music=False)
                for vrow in vids[:2]:
                    card = yt.card_from_video_row(
                        vrow, {"status": vrow.get("status"), "rail_meta": ch["channel_title"]}
                    )
                    items.append(card)
                    if len(items) >= limit:
                        break
                if len(items) >= limit:
                    break
            return jsonify(
                {
                    "ok": True,
                    "rail": rail_id,
                    "items": items[:limit],
                    "hint": "Все каналы — в разделе «Каналы»",
                }
            )

        if rail_id == "continue_vibe":
            recent = db.fetchall(
                """
                SELECT v.* FROM library_items li
                JOIN videos v ON v.video_id = li.video_id
                WHERE li.user_id = ? AND li.status = 'watched'
                ORDER BY COALESCE(li.watched_at, li.saved_at) DESC LIMIT 5
                """,
                (uid,),
            )
            if not recent:
                recent = db.fetchall(
                    """
                    SELECT v.* FROM watch_events we
                    JOIN videos v ON v.video_id = we.video_id
                    WHERE we.user_id = ?
                    ORDER BY we.at DESC LIMIT 5
                    """,
                    (uid,),
                )
            pool = db.fetchall(
                """
                SELECT v.*, li.status, li.saved_at, li.watched_at
                FROM library_items li JOIN videos v ON v.video_id = li.video_id
                WHERE li.user_id = ? AND li.status = 'queue'
                """,
                (uid,),
            )
            pool = _clean_lib_rows(pool, allow_music=False, allow_shorts=False)
            pool_cards = []
            for r in pool:
                c = yt.card_from_video_row(r, {"status": r.get("status")})
                c["tags"] = sim.parse_tags_json(r.get("tags_json"))
                pool_cards.append(c)
            scored: dict[str, float] = {}
            best: dict[str, dict] = {}
            for a_row in recent:
                a = yt.card_from_video_row(a_row)
                a["tags"] = sim.parse_tags_json(a_row.get("tags_json"))
                for c in sim.rank_similar(a, pool_cards, limit=12):
                    vid = c["video_id"]
                    sc = float(c.get("similarity") or 0)
                    if sc > scored.get(vid, 0):
                        scored[vid] = sc
                        best[vid] = c
            items = sorted(best.values(), key=lambda x: -float(x.get("similarity") or 0))
            return jsonify({"ok": True, "rail": rail_id, "items": items[:limit]})

        if rail_id == "for_this_hour":
            hour = datetime.now(timezone.utc).hour
            # SQLite / PG: extract hour from watch_events
            if db.is_postgres():
                rows = db.fetchall(
                    """
                    SELECT v.*, li.status, li.saved_at, li.watched_at, COUNT(*) AS hits
                    FROM watch_events we
                    JOIN videos v ON v.video_id = we.video_id
                    LEFT JOIN library_items li
                      ON li.video_id = we.video_id AND li.user_id = we.user_id
                    WHERE we.user_id = ? AND EXTRACT(HOUR FROM we.at) = ?
                    GROUP BY v.video_id, li.status, li.saved_at, li.watched_at
                    ORDER BY hits DESC LIMIT ?
                    """,
                    (uid, hour, limit),
                )
            else:
                rows = db.fetchall(
                    """
                    SELECT v.*, li.status, li.saved_at, li.watched_at, COUNT(*) AS hits
                    FROM watch_events we
                    JOIN videos v ON v.video_id = we.video_id
                    LEFT JOIN library_items li
                      ON li.video_id = we.video_id AND li.user_id = we.user_id
                    WHERE we.user_id = ?
                      AND CAST(strftime('%H', we.at) AS INTEGER) = ?
                    GROUP BY v.video_id
                    ORDER BY hits DESC LIMIT ?
                    """,
                    (uid, hour, limit),
                )
            # fallback: queue if no history
            if not rows:
                rows = db.fetchall(
                    """
                    SELECT v.*, li.status, li.saved_at, li.watched_at
                    FROM library_items li JOIN videos v ON v.video_id = li.video_id
                    WHERE li.user_id = ? AND li.status = 'queue'
                    ORDER BY li.saved_at DESC LIMIT ?
                    """,
                    (uid, max(limit * 12, 80)),
                )
            rows = _clean_lib_rows(rows, allow_music=False, allow_shorts=False)[:limit]
            return jsonify({"ok": True, "rail": rail_id, "items": _cards_from_lib_rows(rows)})

        return json_error("Неизвестный rail", 404)

    # ----- Lists & tags -----

    @app.get("/api/lists")
    @require_auth
    def get_lists():
        uid = current_user()["user_id"]
        rows = db.fetchall(
            "SELECT * FROM lists WHERE user_id = ? ORDER BY created_at DESC",
            (uid,),
        )
        out = []
        for r in rows:
            cnt = db.fetchone(
                "SELECT COUNT(*) AS c FROM list_items WHERE list_id = ?",
                (r["id"],),
            )
            out.append(
                {
                    "id": r["id"],
                    "title": r["title"],
                    "created_at": str(r.get("created_at") or ""),
                    "count": int((cnt or {}).get("c") or 0),
                }
            )
        return jsonify({"ok": True, "lists": out})

    @app.post("/api/lists")
    @require_auth
    def create_list():
        uid = current_user()["user_id"]
        body = request.get_json(silent=True) or {}
        title = (body.get("title") or "").strip()[:120]
        if not title:
            return json_error("Нужно название")
        if db.is_postgres():
            with db.connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO lists (user_id, title) VALUES (%s, %s) RETURNING id, title, created_at",
                        (uid, title),
                    )
                    r = cur.fetchone()
                    return jsonify(
                        {
                            "ok": True,
                            "list": {
                                "id": r[0],
                                "title": r[1],
                                "created_at": str(r[2]),
                                "count": 0,
                            },
                        }
                    )
        db.execute("INSERT INTO lists (user_id, title) VALUES (?, ?)", (uid, title))
        row = db.fetchone(
            "SELECT * FROM lists WHERE user_id = ? AND title = ? ORDER BY id DESC",
            (uid, title),
        )
        return jsonify(
            {
                "ok": True,
                "list": {
                    "id": row["id"],
                    "title": row["title"],
                    "created_at": str(row.get("created_at") or ""),
                    "count": 0,
                },
            }
        )

    @app.get("/api/lists/<int:list_id>")
    @require_auth
    def list_detail(list_id: int):
        uid = current_user()["user_id"]
        lst = db.fetchone(
            "SELECT * FROM lists WHERE id = ? AND user_id = ?",
            (list_id, uid),
        )
        if not lst:
            return json_error("Список не найден", 404)
        rows = db.fetchall(
            """
            SELECT v.*, li.status, li.saved_at
            FROM list_items x
            JOIN videos v ON v.video_id = x.video_id
            LEFT JOIN library_items li
              ON li.video_id = x.video_id AND li.user_id = ?
            WHERE x.list_id = ?
            ORDER BY x.position ASC, x.added_at DESC
            """,
            (uid, list_id),
        )
        return jsonify(
            {
                "ok": True,
                "list": {"id": lst["id"], "title": lst["title"]},
                "items": _cards_from_lib_rows(rows),
            }
        )

    @app.post("/api/lists/<int:list_id>/items")
    @require_auth
    def list_add_item(list_id: int):
        uid = current_user()["user_id"]
        body = request.get_json(silent=True) or {}
        video_id = (body.get("video_id") or "").strip()
        if not video_id:
            return json_error("Нужен video_id")
        _add_to_list(uid, list_id, video_id)
        return jsonify({"ok": True})

    DEFAULT_TAGS = [
        ("готовка", "🍳"),
        ("музыка", "🎵"),
        ("обучение", "📚"),
        ("обзоры", "🔎"),
        ("игры", "🎮"),
        ("новости", "📰"),
        ("подкаст", "🎙"),
        ("юмор", "😂"),
        ("спорт", "⚽️"),
        ("кино", "🎬"),
    ]

    @app.get("/api/tags")
    @require_auth
    def get_tags():
        uid = current_user()["user_id"]
        rows = db.fetchall(
            "SELECT * FROM user_tags WHERE user_id = ? ORDER BY name",
            (uid,),
        )
        return jsonify({"ok": True, "tags": rows, "llm": llm.available()})

    @app.post("/api/tags")
    @require_auth
    def create_tag():
        uid = current_user()["user_id"]
        body = request.get_json(silent=True) or {}
        name = (body.get("name") or "").strip()[:60]
        if not name:
            return json_error("Нужно имя тега")
        emoji = (body.get("emoji") or "").strip()[:8]
        existing = db.fetchone(
            "SELECT * FROM user_tags WHERE user_id = ? AND name = ?",
            (uid, name),
        )
        if existing:
            return jsonify({"ok": True, "tag": existing, "created": False})
        if db.is_postgres():
            with db.connect() as conn:
                cur = conn.execute(
                    "INSERT INTO user_tags (user_id, name, emoji) VALUES (%s, %s, %s) "
                    "RETURNING id, user_id, name, emoji, color",
                    (uid, name, emoji),
                )
                row = dict(cur.fetchone())
        else:
            db.execute(
                "INSERT INTO user_tags (user_id, name, emoji) VALUES (?, ?, ?)",
                (uid, name, emoji),
            )
            row = db.fetchone(
                "SELECT * FROM user_tags WHERE user_id = ? AND name = ?",
                (uid, name),
            )
        return jsonify({"ok": True, "tag": row, "created": True})

    @app.post("/api/tags/seed-defaults")
    @require_auth
    def seed_default_tags():
        uid = current_user()["user_id"]
        created = 0
        for name, emoji in DEFAULT_TAGS:
            exists = db.fetchone(
                "SELECT id FROM user_tags WHERE user_id = ? AND name = ?",
                (uid, name),
            )
            if exists:
                continue
            db.execute(
                "INSERT INTO user_tags (user_id, name, emoji) VALUES (?, ?, ?)",
                (uid, name, emoji),
            )
            created += 1
        rows = db.fetchall(
            "SELECT * FROM user_tags WHERE user_id = ? ORDER BY name",
            (uid,),
        )
        return jsonify({"ok": True, "created": created, "tags": rows})

    @app.delete("/api/tags/<int:tag_id>")
    @require_auth
    def delete_tag(tag_id: int):
        uid = current_user()["user_id"]
        row = db.fetchone(
            "SELECT * FROM user_tags WHERE id = ? AND user_id = ?",
            (tag_id, uid),
        )
        if not row:
            return json_error("Тег не найден", 404)
        db.execute("DELETE FROM item_tags WHERE user_id = ? AND tag_id = ?", (uid, tag_id))
        db.execute("DELETE FROM user_tags WHERE id = ? AND user_id = ?", (tag_id, uid))
        return jsonify({"ok": True})

    @app.post("/api/videos/<video_id>/tags")
    @require_auth
    def tag_video(video_id: str):
        uid = current_user()["user_id"]
        body = request.get_json(silent=True) or {}
        name = (body.get("name") or "").strip()
        tag_id = body.get("tag_id")
        if tag_id and not name:
            tag = db.fetchone(
                "SELECT * FROM user_tags WHERE id = ? AND user_id = ?",
                (int(tag_id), uid),
            )
            if not tag:
                return json_error("Тег не найден", 404)
            name = tag["name"]
        if not name:
            return json_error("Нужен тег")
        # video must be in library
        if not db.fetchone(
            "SELECT video_id FROM library_items WHERE user_id = ? AND video_id = ?",
            (uid, video_id),
        ):
            return json_error("Сначала добавь видео в библиотеку", 400)
        try:
            tag = _ensure_tag_on_item(uid, video_id, name, emoji=(body.get("emoji") or ""))
        except ValueError as e:
            return json_error(str(e), 400)
        item = _library_card(uid, video_id)
        return jsonify({"ok": True, "tag": tag, "item": item, "user_tags": (item or {}).get("user_tags")})

    @app.delete("/api/videos/<video_id>/tags/<int:tag_id>")
    @require_auth
    def untag_video(video_id: str, tag_id: int):
        uid = current_user()["user_id"]
        db.execute(
            "DELETE FROM item_tags WHERE user_id = ? AND video_id = ? AND tag_id = ?",
            (uid, video_id, tag_id),
        )
        return jsonify({"ok": True, "item": _library_card(uid, video_id)})

    @app.post("/api/videos/<video_id>/suggest-themes")
    @require_auth
    def suggest_themes(video_id: str):
        uid = current_user()["user_id"]
        row = db.fetchone("SELECT * FROM videos WHERE video_id = ?", (video_id,))
        if not row:
            return json_error("Нет видео", 404)
        tags = db.fetchall(
            "SELECT name FROM user_tags WHERE user_id = ? ORDER BY name",
            (uid,),
        )
        lists = db.fetchall(
            "SELECT title FROM lists WHERE user_id = ? ORDER BY title",
            (uid,),
        )
        suggestion = llm.suggest_video_themes(
            title=row.get("title") or "",
            channel=row.get("channel_title") or "",
            description=row.get("description") or "",
            existing_tags=[t["name"] for t in tags],
            existing_lists=[l["title"] for l in lists],
        )
        apply = bool((request.get_json(silent=True) or {}).get("apply"))
        applied = {"tags": [], "list_id": None}
        if apply:
            for name in suggestion.get("tags") or []:
                try:
                    applied["tags"].append(
                        _ensure_tag_on_item(uid, video_id, name)
                    )
                except Exception:
                    pass
            list_title = suggestion.get("list_title")
            if list_title:
                existing = db.fetchone(
                    "SELECT id FROM lists WHERE user_id = ? AND title = ?",
                    (uid, list_title),
                )
                if existing:
                    list_id = int(existing["id"])
                elif db.is_postgres():
                    with db.connect() as conn:
                        cur = conn.execute(
                            "INSERT INTO lists (user_id, title) VALUES (%s, %s) RETURNING id",
                            (uid, list_title),
                        )
                        list_id = int(cur.fetchone()["id"])
                else:
                    db.execute(
                        "INSERT INTO lists (user_id, title) VALUES (?, ?)",
                        (uid, list_title),
                    )
                    list_id = int(
                        db.fetchone(
                            "SELECT id FROM lists WHERE user_id = ? AND title = ?",
                            (uid, list_title),
                        )["id"]
                    )
                _add_to_list(uid, list_id, video_id)
                applied["list_id"] = list_id
        return jsonify(
            {
                "ok": True,
                "suggestion": suggestion,
                "applied": applied if apply else None,
                "item": _library_card(uid, video_id),
            }
        )

    # ----- Static SPA -----

    @app.get("/")
    @app.get("/home")
    @app.get("/queue")
    @app.get("/channels")
    @app.get("/lists")
    @app.get("/tags")
    @app.get("/add")
    @app.get("/organize")
    @app.get("/onboard")
    @app.get("/auth/callback")
    @app.get("/v/<path:rest>")
    @app.get("/login")
    def spa(rest: str = ""):
        return send_from_directory(WEB, "index.html")

    @app.get("/manifest.webmanifest")
    def manifest():
        return send_from_directory(WEB, "manifest.webmanifest")

    @app.get("/assets/<path:filename>")
    def assets(filename: str):
        return send_from_directory(WEB, filename)

    @app.get("/<path:filename>")
    def web_file(filename: str):
        # allow styles.css / app.js at root of web/
        target = WEB / filename
        if target.is_file() and target.resolve().is_relative_to(WEB.resolve()):
            return send_from_directory(WEB, filename)
        return send_from_directory(WEB, "index.html")

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT") or 8765)
    app.run(host="0.0.0.0", port=port, debug=True)
