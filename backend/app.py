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

from backend import auth, db, digest_jobs, google_oauth, llm, metrics, now_plan, organize, push, reminders_svc, search as cq_search, share_classify, sync_jobs, takeout, themes, yt_sync
from backend import classify_jobs
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

    def session_response(session: dict):
        """JSON + httpOnly cookie so redeploys / cleared Bearer still keep login."""
        resp = jsonify({"ok": True, **session})
        token = session.get("token") or ""
        if token:
            resp.set_cookie(
                "cq_session",
                token,
                max_age=60 * 24 * 3600,
                httponly=True,
                secure=True,
                samesite="Lax",
                path="/",
            )
        return resp

    def clear_session_cookie(resp):
        resp.set_cookie(
            "cq_session",
            "",
            max_age=0,
            httponly=True,
            secure=True,
            samesite="Lax",
            path="/",
        )
        return resp

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
        fcm_env = bool(
            (os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON") or "").strip()
            or (os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH") or "").strip()
        )
        return jsonify(
            {
                "ok": True,
                "service": "clip_queue",
                "version": "0.4.1",
                "db": "postgres" if db.is_postgres() else "sqlite",
                "google_oauth": google_oauth.configured(),
                "llm": llm.available(),
                "youtube_api_key": bool((os.environ.get("YOUTUBE_API_KEY") or "").strip()),
                "fcm_configured": fcm_env,
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
        return session_response(session)

    @app.post("/api/auth/dev-login")
    def dev_login():
        if not auth.dev_login_enabled():
            return json_error("DEV_LOGIN выключен", 403)
        user = auth.ensure_dev_user()
        session = auth.create_session(int(user["id"]))
        return session_response(session)

    @app.post("/api/auth/logout")
    def logout():
        header = request.headers.get("Authorization") or ""
        token = header or request.cookies.get("cq_session") or ""
        if token:
            auth.destroy_session(token)
        resp = jsonify({"ok": True})
        return clear_session_cookie(resp)

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

    @app.post("/api/devices/register")
    @require_auth
    def devices_register():
        uid = current_user()["user_id"]
        body = request.get_json(silent=True) or {}
        token = (body.get("token") or "").strip()
        platform = (body.get("platform") or "android").strip()
        try:
            push.register_device(uid, token, platform=platform)
        except ValueError as e:
            return json_error(str(e), 400)
        return jsonify({"ok": True})

    @app.delete("/api/devices/register")
    @require_auth
    def devices_unregister():
        uid = current_user()["user_id"]
        body = request.get_json(silent=True) or {}
        token = (body.get("token") or request.args.get("token") or "").strip()
        push.unregister_device(uid, token)
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
        client = (request.args.get("client") or "").strip().lower()
        try:
            url = google_oauth.start_url(client=client or None)
        except Exception as e:
            return json_error(str(e), 503)
        return redirect(url)

    @app.get("/api/auth/google/callback")
    def google_callback():
        err = request.args.get("error")
        state = request.args.get("state") or ""
        android = google_oauth.is_android_state(state)
        if err:
            if android:
                return redirect(
                    f"{google_oauth.public_origin()}/api/auth/android/done"
                    f"?error={err}"
                )
            return redirect(f"/login?error={err}")
        code = request.args.get("code") or ""
        try:
            session = google_oauth.login_with_code(code, state)
        except Exception as e:
            if android:
                return redirect(
                    f"{google_oauth.public_origin()}/api/auth/android/done"
                    f"?error={str(e)[:120]}"
                )
            return redirect(f"/login?error={str(e)[:120]}")
        uid = int(session["user"]["id"])
        lib = db.fetchone(
            "SELECT COUNT(*) AS c FROM library_items WHERE user_id = ?",
            (uid,),
        )
        # Autosync only on empty library (onboarding). Returning users → home.
        autosync = 0 if int((lib or {}).get("c") or 0) > 0 else 1
        if android:
            # HTTPS bridge — Custom Tabs often ignore raw clipqueue:// redirects.
            dest = (
                f"{google_oauth.public_origin()}/api/auth/android/done"
                f"?token={session['token']}&autosync={autosync}"
            )
            resp = redirect(dest)
        else:
            resp = redirect(f"/auth/callback?token={session['token']}&autosync={autosync}")
        resp.set_cookie(
            "cq_session",
            session["token"],
            max_age=60 * 24 * 3600,
            httponly=True,
            secure=True,
            samesite="Lax",
            path="/",
        )
        return resp

    @app.post("/api/youtube/sync")
    @require_auth
    def youtube_sync():
        """Start background sync (delta by default; full=1 for deep crawl)."""
        uid = current_user()["user_id"]
        body = request.get_json(silent=True) or {}
        full = (
            str(request.args.get("full") or body.get("full") or "").strip() in ("1", "true", "yes")
        )
        if (request.args.get("plain") or "").strip() == "1":
            try:
                log.info("plain sync start user=%s full=%s", uid, full)
                stats = yt_sync.sync_youtube_library(uid, full=full)
                log.info("plain sync done user=%s", uid)
            except Exception as e:
                log.exception("plain sync failed user=%s", uid)
                return json_error(str(e), 502)
            return jsonify({"ok": True, "stats": stats})

        job = sync_jobs.start_youtube_sync(uid, full=full)
        log.info("sync job started user=%s job=%s full=%s", uid, job.get("id"), full)
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

    @app.get("/api/organize/structure")
    @require_auth
    def organize_structure():
        """Last saved folders + recent + growing themes for home."""
        uid = current_user()["user_id"]
        return jsonify({"ok": True, **organize.home_feed(uid)})

    @app.post("/api/organize/classify-pending")
    @require_auth
    def organize_classify_pending():
        """Background: sort new/unfiled queue videos into saved folders."""
        uid = current_user()["user_id"]
        body = request.get_json(silent=True) or {}
        limit = min(300, max(10, int(body.get("limit") or 200)))
        use_llm = body.get("use_llm")
        if use_llm is None:
            use_llm = True
        resume = bool(body.get("resume"))
        job = classify_jobs.start_classify(
            uid, limit=limit, use_llm=bool(use_llm), resume=resume
        )
        return jsonify({"ok": True, "job": job})

    @app.get("/api/organize/classify-pending")
    @require_auth
    def organize_classify_pending_active():
        """Active / paused classify job for this user (for resume UI)."""
        uid = current_user()["user_id"]
        job = classify_jobs.active_job_for_user(uid)
        return jsonify({"ok": True, "job": job})

    @app.get("/api/organize/classify-pending/<job_id>")
    @require_auth
    def organize_classify_pending_status(job_id: str):
        uid = current_user()["user_id"]
        job = classify_jobs.get_job(job_id)
        if not job:
            job = classify_jobs.active_job_for_user(uid)
        if not job or int(job.get("user_id") or 0) != uid:
            return json_error("Нет задачи", 404)
        return jsonify({"ok": True, "job": job})

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

    @app.post("/api/organize/retag")
    @require_auth
    def organize_retag():
        """Backfill thematic tags on library videos that have none."""
        uid = current_user()["user_id"]
        body = request.get_json(silent=True) or {}
        limit = min(2000, max(5, int(body.get("limit") or 400)))
        # Heuristic + folders by default — LLM optional (can hang)
        use_llm = bool(body.get("use_llm") or False)
        llm_budget = min(40, max(0, int(body.get("llm_budget") or 10)))
        result = organize.retag_library_batch(
            uid, limit=limit, use_llm=use_llm, llm_budget=llm_budget
        )
        return jsonify(result)

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

    @app.post("/api/lists/reorder")
    @require_auth
    def lists_reorder():
        uid = current_user()["user_id"]
        body = request.get_json(silent=True) or {}
        order = body.get("order") or body.get("list_ids") or []
        if not isinstance(order, list) or not order:
            return json_error("Нужен order: [list_id, ...]")
        n = 0
        for i, lid in enumerate(order):
            try:
                list_id = int(lid)
            except (TypeError, ValueError):
                continue
            db.execute(
                "UPDATE lists SET sort_order = ? WHERE id = ? AND user_id = ?",
                (i * 10, list_id, uid),
            )
            n += 1
        return jsonify({"ok": True, "count": n, "updated": n})

    @app.post("/api/library/<video_id>/interest")
    @require_auth
    def set_interest(video_id: str):
        uid = current_user()["user_id"]
        body = request.get_json(silent=True) or {}
        try:
            level = int(body.get("interest") or 0)
        except (TypeError, ValueError):
            level = 0
        level = max(-1, min(2, level))  # -1 less, 0 normal, 1 interesting, 2 very
        row = db.fetchone(
            "SELECT video_id FROM library_items WHERE user_id = ? AND video_id = ?",
            (uid, video_id),
        )
        if not row:
            return json_error("Нет в библиотеке", 404)
        bumped = _apply_interest_and_queue_boost(uid, video_id, level)
        return jsonify({"ok": True, "interest": level, "boosted": bumped})

    def _bump_saved_at(uid: int, video_id: str, *, days_delta: int = 0) -> None:
        """Move item toward (days_delta>=0 as now) or away from queue head."""
        from datetime import datetime, timedelta, timezone

        when = datetime.now(timezone.utc) + timedelta(days=days_delta)
        stamp = when.strftime("%Y-%m-%d %H:%M:%S")
        if db.is_postgres():
            db.execute(
                "UPDATE library_items SET saved_at = %s::timestamptz "
                "WHERE user_id = %s AND video_id = %s AND status IN ('queue', 'in_progress')",
                (when.isoformat(), uid, video_id),
            )
        else:
            db.execute(
                "UPDATE library_items SET saved_at = ? "
                "WHERE user_id = ? AND video_id = ? AND status IN ('queue', 'in_progress')",
                (stamp, uid, video_id),
            )

    def _apply_interest_and_queue_boost(uid: int, video_id: str, level: int) -> list[str]:
        """Set interest, reorder queue via saved_at, softly boost/demote similar."""
        db.execute(
            "UPDATE library_items SET interest = ? WHERE user_id = ? AND video_id = ?",
            (level, uid, video_id),
        )
        if level >= 2:
            _bump_saved_at(uid, video_id, days_delta=0)
        elif level == 1:
            _bump_saved_at(uid, video_id, days_delta=0)
        elif level < 0:
            _bump_saved_at(uid, video_id, days_delta=-10)

        boosted: list[str] = [video_id]
        # Nearby similar from library (same channel + shared tags), queue only
        anchor = db.fetchone("SELECT channel_title FROM videos WHERE video_id = ?", (video_id,))
        ch = (anchor or {}).get("channel_title") or ""
        tag_ids = {
            r["tag_id"]
            for r in db.fetchall(
                "SELECT tag_id FROM item_tags WHERE user_id = ? AND video_id = ?",
                (uid, video_id),
            )
        }
        candidates = db.fetchall(
            """
            SELECT li.video_id, li.interest, v.channel_title
            FROM library_items li
            JOIN videos v ON v.video_id = li.video_id
            WHERE li.user_id = ? AND li.video_id != ?
              AND li.status = 'queue'
            ORDER BY li.saved_at DESC
            LIMIT 80
            """,
            (uid, video_id),
        )
        scored: list[tuple[int, str]] = []
        for c in candidates:
            score = 0
            if ch and (c.get("channel_title") or "") == ch:
                score += 3
            if tag_ids:
                shared = db.fetchone(
                    """
                    SELECT COUNT(*) AS n FROM item_tags
                    WHERE user_id = ? AND video_id = ? AND tag_id IN ({})
                    """.format(",".join("?" * len(tag_ids))),
                    (uid, c["video_id"], *tag_ids),
                ) if tag_ids else None
                score += int((shared or {}).get("n") or 0)
            if score > 0:
                scored.append((score, c["video_id"]))
        scored.sort(reverse=True)
        for _, sid in scored[:5]:
            cur = db.fetchone(
                "SELECT interest FROM library_items WHERE user_id = ? AND video_id = ?",
                (uid, sid),
            )
            cur_i = int((cur or {}).get("interest") or 0)
            if level >= 2:
                new_i = min(2, max(cur_i, 1))
                db.execute(
                    "UPDATE library_items SET interest = ? WHERE user_id = ? AND video_id = ?",
                    (new_i, uid, sid),
                )
                _bump_saved_at(uid, sid, days_delta=0)
                boosted.append(sid)
            elif level == 1:
                _bump_saved_at(uid, sid, days_delta=0)
                boosted.append(sid)
            elif level < 0:
                new_i = max(-1, cur_i - 1)
                db.execute(
                    "UPDATE library_items SET interest = ? WHERE user_id = ? AND video_id = ?",
                    (new_i, uid, sid),
                )
                _bump_saved_at(uid, sid, days_delta=-5)
                boosted.append(sid)
        return boosted

    @app.post("/api/library/<video_id>/dismiss")
    @require_auth
    def dismiss_video(video_id: str):
        """Hide forever — sync will not bring it back."""
        uid = current_user()["user_id"]
        db.execute(
            "UPDATE library_items SET status = 'dismissed' WHERE user_id = ? AND video_id = ?",
            (uid, video_id),
        )
        db.execute(
            "DELETE FROM list_items WHERE video_id = ? AND list_id IN "
            "(SELECT id FROM lists WHERE user_id = ?)",
            (video_id, uid),
        )
        return jsonify({"ok": True})

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

        # Music/clips never enter the planning queue
        if (
            yt.content_bucket(
                meta.get("title"),
                meta.get("channel_title"),
                meta.get("duration_sec"),
                meta.get("description"),
            )
            == "music"
            and status == "queue"
        ):
            status = "archived"

        existing = db.fetchone(
            "SELECT * FROM library_items WHERE user_id = ? AND video_id = ?",
            (uid, vid),
        )
        if existing:
            # Always bump saved_at so share/paste lands in «Недавно»
            if db.is_postgres():
                db.execute(
                    "UPDATE library_items SET status = ?, note = ?, source = ?, "
                    "saved_at = NOW() WHERE user_id = ? AND video_id = ?",
                    (status, note or existing.get("note") or "", source, uid, vid),
                )
            else:
                db.execute(
                    "UPDATE library_items SET status = ?, note = ?, source = ?, "
                    "saved_at = datetime('now') WHERE user_id = ? AND video_id = ?",
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

        # Classification: sync (default for paste) or async (share / classify_async)
        apply_class = body.get("apply_classification")
        if apply_class is None:
            apply_class = True
        classify_async = body.get("classify_async")
        if classify_async is None:
            classify_async = source in ("android_share", "share_target", "pwa_share")
        classify_async = bool(classify_async)

        matched = []
        classify_meta = {"engine": "none", "reason": ""}
        queued_async = False
        if apply_class and classify_async:
            share_classify.enqueue_after_save(
                uid,
                vid,
                source=source,
                title=(meta.get("title") or ""),
                channel_title=(meta.get("channel_title") or ""),
                thumb_url=(meta.get("thumb_url") or yt.thumb_url(vid)),
                duration_sec=meta.get("duration_sec"),
                description=(meta.get("description") or ""),
            )
            queued_async = True
            classify_meta = {"engine": "pending", "reason": "async"}
        elif apply_class:
            classify_meta = organize.classify_new_video(
                uid,
                vid,
                title=meta.get("title"),
                channel_title=meta.get("channel_title"),
                duration_sec=meta.get("duration_sec"),
                description=meta.get("description"),
            )
            matched = classify_meta.get("matched") or []

        item = _library_card(uid, vid)
        classified_into = [
            {"list_id": m["list_id"], "list_title": m.get("list_title")}
            for m in matched
        ]
        in_lists = _lists_for_video(uid, vid)
        tags = (item or {}).get("user_tags") or []
        if not queued_async:
            try:
                _record_save_event(
                    uid,
                    vid,
                    source=source,
                    title=(meta.get("title") or ""),
                    channel_title=(meta.get("channel_title") or ""),
                    thumb_url=(meta.get("thumb_url") or yt.thumb_url(vid)),
                    classified_into=classified_into,
                    tags=tags,
                    lists=in_lists,
                    classify_engine=str(classify_meta.get("engine") or ""),
                    classify_reason=str(classify_meta.get("reason") or ""),
                )
            except Exception as e:
                log.warning("save_event record failed: %s", e)
        return jsonify(
            {
                "ok": True,
                "item": item,
                "video_id": vid,
                "title": meta.get("title") or "",
                "classified_into": classified_into,
                "in_lists": in_lists,
                "tags": tags,
                "classify_engine": classify_meta.get("engine"),
                "classify_reason": classify_meta.get("reason"),
                "classify_async": queued_async,
            }
        )

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
                "in_lists": _lists_for_video(uid, video_id),
            },
        )

    @app.get("/api/saves/history")
    @require_auth
    def saves_history():
        """Recent save + classify results for debug."""
        uid = current_user()["user_id"]
        limit = min(100, max(1, int(request.args.get("limit") or 40)))
        try:
            rows = db.fetchall(
                """
                SELECT * FROM save_events
                WHERE user_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (uid, limit),
            )
        except Exception as e:
            log.warning("save_events query failed (table missing?): %s", e)
            rows = []
        events = []
        for r in rows:
            def _parse(key: str):
                raw = r.get(key) or "[]"
                if isinstance(raw, (list, dict)):
                    return raw
                try:
                    return json.loads(raw)
                except Exception:
                    return []

            events.append(
                {
                    "id": r.get("id"),
                    "video_id": r.get("video_id"),
                    "title": r.get("title") or "",
                    "channel_title": r.get("channel_title") or "",
                    "thumb_url": r.get("thumb_url") or "",
                    "source": r.get("source") or "",
                    "classified_into": _parse("classified_json"),
                    "tags": _parse("tags_json"),
                    "in_lists": _parse("lists_json"),
                    "classify_engine": r.get("classify_engine") or "",
                    "classify_reason": r.get("classify_reason") or "",
                    "created_at": str(r.get("created_at") or ""),
                }
            )
        return jsonify({"ok": True, "events": events})

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
        theme = (request.args.get("theme") or "").strip().lower()
        try:
            tag_id = int(request.args.get("tag_id") or 0)
        except ValueError:
            tag_id = 0
        tag_name = (request.args.get("tag") or "").strip().lower()
        try:
            dur_min = int(request.args.get("dur_min") or 0)
        except ValueError:
            dur_min = 0
        try:
            dur_max = int(request.args.get("dur_max") or 0)
        except ValueError:
            dur_max = 0
        limit = min(int(request.args.get("limit") or 60), 200)
        offset = max(int(request.args.get("offset") or 0), 0)
        # Over-fetch then filter — junk buckets otherwise fill the page
        fetch_n = min(3000, max(limit * 30, 300))
        if status in ("", "all", "*"):
            rows = db.fetchall(
                """
                SELECT v.*, li.status, li.note, li.source, li.saved_at, li.watched_at, li.interest
                FROM library_items li
                JOIN videos v ON v.video_id = li.video_id
                WHERE li.user_id = ?
                  AND li.status IN ('queue', 'in_progress', 'watched')
                ORDER BY COALESCE(li.interest, 0) DESC, li.saved_at DESC
                LIMIT ?
                """,
                (uid, fetch_n),
            )
        else:
            rows = db.fetchall(
                """
                SELECT v.*, li.status, li.note, li.source, li.saved_at, li.watched_at, li.interest
                FROM library_items li
                JOIN videos v ON v.video_id = li.video_id
                WHERE li.user_id = ? AND li.status = ?
                ORDER BY COALESCE(li.interest, 0) DESC, li.saved_at DESC
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
            dur = row.get("duration_sec")
            if dur_min > 0 and (not isinstance(dur, int) or int(dur) < dur_min):
                continue
            if dur_max > 0 and (not isinstance(dur, int) or int(dur) > dur_max):
                continue
            if theme:
                primary = themes.primary_theme(row.get("title"), row.get("channel_title"))
                if not primary or primary.get("id") != theme:
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
            if tag_id and not any(int(t["id"]) == tag_id for t in tags):
                continue
            if tag_name and not any(tag_name in (t.get("name") or "").lower() for t in tags):
                continue
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
        return jsonify(
            {
                "ok": True,
                "items": page,
                "kind": kind,
                "channel": channel or None,
                "theme": theme or None,
                "dur_min": dur_min or None,
                "dur_max": dur_max or None,
            }
        )

    @app.get("/api/channels")
    @require_auth
    def channels():
        """Channels with optional inline videos, theme + duration filters."""
        uid = current_user()["user_id"]
        kind = (request.args.get("kind") or "video").strip().lower()
        status = (request.args.get("status") or "queue").strip()
        theme = (request.args.get("theme") or "").strip().lower()
        expand = request.args.get("expand") in ("1", "true", "yes")
        try:
            dur_min = int(request.args.get("dur_min") or 0)
        except ValueError:
            dur_min = 0
        try:
            dur_max = int(request.args.get("dur_max") or 0)
        except ValueError:
            dur_max = 0
        try:
            videos_limit = min(int(request.args.get("videos_limit") or 16), 40)
        except ValueError:
            videos_limit = 16

        rows = db.fetchall(
            """
            SELECT v.video_id, v.title, v.channel_id, v.channel_title,
                   v.duration_sec, v.thumb_url, v.description
            FROM library_items li
            JOIN videos v ON v.video_id = li.video_id
            WHERE li.user_id = ? AND li.status = ?
            ORDER BY li.saved_at DESC
            """,
            (uid, status),
        )
        sub_by_id: dict[str, str] = {}
        sub_by_title: dict[str, str] = {}
        try:
            for s in db.fetchall(
                "SELECT channel_id, channel_title, thumb_url FROM subscriptions WHERE user_id = ?",
                (uid,),
            ):
                if s.get("thumb_url"):
                    if s.get("channel_id"):
                        sub_by_id[str(s["channel_id"])] = s["thumb_url"]
                    if s.get("channel_title"):
                        sub_by_title[str(s["channel_title"]).strip()] = s["thumb_url"]
        except Exception:
            pass

        buckets: dict[str, dict] = {}
        for r in rows:
            title = (r.get("channel_title") or "Без канала").strip() or "Без канала"
            if yt.is_unavailable_video(r.get("title")) or yt.is_unavailable_video(title):
                continue
            bucket = yt.content_bucket(
                r.get("title"),
                title,
                r.get("duration_sec"),
                r.get("description"),
            )
            if kind == "video" and bucket != "video":
                continue
            if kind == "music" and bucket != "music":
                continue
            if kind in ("shorts", "shortform") and bucket not in ("shorts", "shortform"):
                continue
            if kind == "marathon" and bucket != "marathon":
                continue
            if kind not in ("all", "video", "music", "shorts", "shortform", "marathon"):
                pass
            if kind == "all":
                pass
            dur = r.get("duration_sec")
            if dur_min > 0 and (not isinstance(dur, int) or int(dur) < dur_min):
                continue
            if dur_max > 0 and (not isinstance(dur, int) or int(dur) > dur_max):
                continue
            if theme:
                primary = themes.primary_theme(r.get("title"), title)
                if not primary or primary.get("id") != theme:
                    continue

            key = f"{r.get('channel_id') or ''}|{title}"
            slot = buckets.get(key)
            if not slot:
                ch_id = (r.get("channel_id") or "").strip()
                thumb = (
                    sub_by_id.get(ch_id)
                    or sub_by_title.get(title)
                    or r.get("thumb_url")
                    or yt.thumb_url(r.get("video_id") or "")
                )
                slot = {
                    "channel_id": r.get("channel_id") or "",
                    "channel_title": title,
                    "count": 0,
                    "thumb_url": thumb,
                    "is_music": bucket == "music",
                    "videos": [],
                }
                buckets[key] = slot
            slot["count"] += 1
            if expand and len(slot["videos"]) < videos_limit:
                slot["videos"].append(
                    {
                        "video_id": r["video_id"],
                        "title": r.get("title") or r["video_id"],
                        "channel_title": title,
                        "duration_sec": r.get("duration_sec"),
                        "duration_label": yt.format_duration(r.get("duration_sec")),
                        "thumb_url": r.get("thumb_url") or yt.thumb_url(r["video_id"]),
                        "watch_url": f"https://www.youtube.com/watch?v={r['video_id']}",
                        "content_kind": bucket,
                    }
                )
        out = sorted(buckets.values(), key=lambda x: -int(x["count"]))
        return jsonify(
            {
                "ok": True,
                "channels": out,
                "kind": kind,
                "theme": theme or None,
                "dur_min": dur_min or None,
                "dur_max": dur_max or None,
                "themes": [{"id": t["id"], "title": t["title"]} for t in themes.THEMES],
            }
        )

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
        if status in ("queue", "in_progress", "watched", "archived", "dismissed"):
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
            elif status == "dismissed":
                # Soft-delete: out of all user lists, sync won't bring it back
                db.execute(
                    "DELETE FROM list_items WHERE video_id = ? AND list_id IN "
                    "(SELECT id FROM lists WHERE user_id = ?)",
                    (video_id, uid),
                )
        if "interest" in body:
            try:
                interest = max(-1, min(2, int(body.get("interest"))))
            except (TypeError, ValueError):
                interest = 0
            boosted = _apply_interest_and_queue_boost(uid, video_id, interest)
            if status not in ("queue", "in_progress", "watched", "archived", "dismissed") and note is None:
                return jsonify({
                    "ok": True,
                    "item": _library_card(uid, video_id),
                    "interest": interest,
                    "boosted": boosted,
                })
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
        body = request.get_json(silent=True) or {}
        surface = (body.get("surface") or request.args.get("surface") or "").strip()
        db.execute(
            "INSERT INTO watch_events (user_id, video_id, event_type) VALUES (?, ?, ?)",
            (uid, video_id, "open_yt"),
        )
        if surface in (
            "now",
            "plan_tonight",
            "plan_week",
            "suggestion",
            "digest",
            "push",
            "reminder",
        ):
            et_map = {
                "now": "now_open",
                "plan_tonight": "plan_open",
                "plan_week": "plan_open",
                "suggestion": "suggestion_open",
                "digest": "digest_open",
                "push": "push_open",
                "reminder": "plan_open",
            }
            metrics.track(uid, et_map.get(surface, "now_open"), video_id=video_id, surface=surface)
            metrics.track(uid, "planned_watch", video_id=video_id, surface=surface)
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
            item["in_lists"] = []
            item["user_tags"] = []
        return jsonify({"ok": True, "item": item})

    @app.get("/api/videos/<video_id>/similar")
    @require_auth
    def similar(video_id: str):
        uid = current_user()["user_id"]
        anchor_row = db.fetchone("SELECT * FROM videos WHERE video_id = ?", (video_id,))
        if not anchor_row:
            return json_error("Нет видео", 404)
        anchor_li = db.fetchone(
            "SELECT note, interest FROM library_items WHERE user_id = ? AND video_id = ?",
            (uid, video_id),
        )
        anchor = yt.card_from_video_row(anchor_row)
        anchor["tags"] = sim.parse_tags_json(anchor_row.get("tags_json"))
        anchor["note"] = (anchor_li or {}).get("note") or ""

        rows = db.fetchall(
            """
            SELECT v.*, li.note AS user_note, li.status AS lib_status
            FROM library_items li
            JOIN videos v ON v.video_id = li.video_id
            WHERE li.user_id = ? AND li.video_id != ?
              AND COALESCE(li.status, 'queue') NOT IN ('dismissed', 'rejected')
            """,
            (uid, video_id),
        )
        candidates = []
        for r in rows:
            c = yt.card_from_video_row(r)
            c["tags"] = sim.parse_tags_json(r.get("tags_json"))
            c["note"] = r.get("user_note") or ""
            candidates.append(c)

        anchor_tag_ids = {
            r["tag_id"]
            for r in db.fetchall(
                "SELECT tag_id FROM item_tags WHERE user_id = ? AND video_id = ?",
                (uid, video_id),
            )
        }
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

        ranked = sim.rank_similar(anchor, candidates, tag_overlap=overlap, limit=18)
        return jsonify({"ok": True, "items": ranked})

    @app.get("/api/videos/<video_id>/yt-related")
    @require_auth
    def yt_related(video_id: str):
        """Topic search on YouTube — no shorts, no library dupes, min topic overlap.

        relatedToVideoId is deprecated; we search with tight queries + duration filter.
        """
        uid = current_user()["user_id"]
        row = db.fetchone("SELECT * FROM videos WHERE video_id = ?", (video_id,))
        if not row:
            return json_error("Нет видео", 404)

        queries = sim.related_search_queries(
            row.get("title") or "",
            row.get("channel_title") or "",
            row.get("description") or "",
        )
        q_primary = queries[0] if queries else (row.get("title") or "")[:80]

        access = ""
        oauth_ok = False
        try:
            access = google_oauth.get_valid_access_token(uid)
            oauth_ok = bool(access)
        except Exception as e:
            print(f"[yt-related] oauth: {e}", flush=True)
        has_key = bool((os.environ.get("YOUTUBE_API_KEY") or "").strip())
        if not has_key and not oauth_ok:
            return jsonify(
                {
                    "ok": True,
                    "query": q_primary,
                    "queries": queries,
                    "items": [],
                    "error": "no_youtube_search_auth",
                    "note": "Нужен YOUTUBE_API_KEY на сервере или вход через Google (YouTube).",
                }
            )

        token = None if has_key else access
        # Already in library → hide from YT rail (incl. «Похожие из твоих»)
        lib_ids = {
            r["video_id"]
            for r in db.fetchall(
                "SELECT video_id FROM library_items WHERE user_id = ?", (uid,)
            )
        }
        exclude = {video_id} | set(lib_ids)
        found: list[dict] = []

        # 1) Topic searches: medium (4–20m) + long (20m+) — skip API «short»
        for q in queries[:2]:
            for dur in ("medium", "long"):
                batch = yt.search_videos(
                    q,
                    max_results=8,
                    exclude_ids=exclude,
                    access_token=token,
                    video_duration=dur,
                )
                found.extend(batch)
                exclude |= {x["video_id"] for x in batch}

        # 2) Same channel, but still with topic words (not random latest uploads)
        ch = (row.get("channel_id") or "").strip()
        topic_toks = [
            t
            for t in sim.tokens(row.get("title") or "")
        ]
        # Prefer longer tokens for channel sibling search
        topic_q = " ".join(sorted(topic_toks, key=lambda t: (-len(t), t))[:4])
        if ch and topic_q:
            batch = yt.search_videos(
                topic_q,
                max_results=6,
                exclude_ids=exclude,
                access_token=token,
                channel_id=ch,
                order="relevance",
                video_duration="medium",
            )
            found.extend(batch)
            exclude |= {x["video_id"] for x in batch}
            batch = yt.search_videos(
                topic_q,
                max_results=4,
                exclude_ids=exclude,
                access_token=token,
                channel_id=ch,
                order="relevance",
                video_duration="long",
            )
            found.extend(batch)

        # Dedup keep order
        seen: set[str] = set()
        uniq: list[dict] = []
        for it in found:
            vid = it["video_id"]
            if vid in seen or vid in lib_ids:
                continue
            title_l = (it.get("title") or "").lower()
            if "#shorts" in title_l or " #short" in title_l:
                continue
            seen.add(vid)
            uniq.append(it)

        # Hard duration cut: drop true shorts / very short clips
        min_sec = 180  # 3+ minutes
        durs = yt.fetch_durations([it["video_id"] for it in uniq], access_token=token)
        lasting: list[dict] = []
        for it in uniq:
            sec = durs.get(it["video_id"])
            if sec is not None and sec < min_sec:
                continue
            if sec is not None:
                it["duration_sec"] = sec
                it["duration_label"] = yt.format_duration(sec)
            lasting.append(it)

        anchor_toks = sim.tokens(
            f"{row.get('title') or ''} {(row.get('description') or '')[:500]}"
        )
        scored: list[dict] = []
        for it in lasting:
            sc = sim.topic_overlap_score(
                anchor_toks,
                it.get("title") or "",
                it.get("description") or "",
            )
            # Drop topical garbage (Comedy Club on «трудности перевода» etc.)
            if sc < 1.15:
                continue
            if it.get("channel_id") and it.get("channel_id") == ch:
                sc += 0.55  # sibling on same channel + topic = good
            it["in_library"] = False
            it["similarity"] = round(sc, 2)
            scored.append(it)
        scored.sort(key=lambda x: -float(x.get("similarity") or 0))
        # Diversify channels a bit
        final: list[dict] = []
        ch_count: dict[str, int] = {}
        for it in scored:
            cid = it.get("channel_id") or "_"
            if ch_count.get(cid, 0) >= 3:
                continue
            ch_count[cid] = ch_count.get(cid, 0) + 1
            final.append(it)
            if len(final) >= 12:
                break

        return jsonify(
            {
                "ok": True,
                "query": q_primary,
                "queries": queries,
                "items": final,
                "auth": "api_key" if has_key else "oauth",
                "note": "По теме и с канала · без шорцов · без уже добавленных",
            }
        )

    @app.get("/api/search")
    @require_auth
    def api_search():
        uid = current_user()["user_id"]
        q = (request.args.get("q") or "").strip()
        if len(q) < 2:
            return json_error("Напиши запрос")
        limit = min(60, max(8, int(request.args.get("limit") or 36)))
        rows = db.fetchall(
            """
            SELECT v.*, li.status, li.note, li.interest
            FROM library_items li
            JOIN videos v ON v.video_id = li.video_id
            WHERE li.user_id = ?
              AND COALESCE(li.status, 'queue') NOT IN ('dismissed', 'rejected')
            """,
            (uid,),
        )
        items = []
        for r in rows:
            card = yt.card_from_video_row(
                r,
                {
                    "status": r.get("status"),
                    "note": r.get("note") or "",
                    "interest": int(r.get("interest") or 0),
                },
            )
            card["tags"] = sim.parse_tags_json(r.get("tags_json"))
            items.append(card)
        # Attach user tags lightly
        from collections import defaultdict

        by_vid: dict[str, list] = defaultdict(list)
        for r in db.fetchall(
            """
            SELECT it.video_id, ut.id, ut.name, ut.emoji
            FROM item_tags it
            JOIN user_tags ut ON ut.id = it.tag_id
            WHERE it.user_id = ?
            """,
            (uid,),
        ):
            by_vid[r["video_id"]].append(
                {"id": r["id"], "name": r["name"], "emoji": r.get("emoji") or ""}
            )
        for it in items:
            it["user_tags"] = by_vid.get(it["video_id"]) or []

        result = cq_search.smart_search(q, items, limit=limit)
        return jsonify({"ok": True, **result})

    @app.post("/api/voice/transcribe")
    @require_auth
    def voice_transcribe():
        """Whisper via OpenAI if OPENAI_API_KEY set; else client should use Web Speech API."""
        import requests as req

        key = (os.environ.get("OPENAI_API_KEY") or "").strip()
        if not key:
            return json_error(
                "Whisper на сервере не настроен (OPENAI_API_KEY). Используй голосовой ввод браузера.",
                503,
            )
        f = request.files.get("audio") or request.files.get("file")
        if not f:
            return json_error("Нужен файл audio")
        raw = f.read()
        if not raw or len(raw) > 12_000_000:
            return json_error("Пустой или слишком большой файл")
        try:
            r = req.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {key}"},
                files={"file": (f.filename or "audio.webm", raw, f.mimetype or "audio/webm")},
                data={"model": "whisper-1", "language": "ru"},
                timeout=60,
            )
        except Exception as e:
            return json_error(f"Whisper недоступен: {e}", 502)
        if r.status_code != 200:
            return json_error(f"Whisper HTTP {r.status_code}: {r.text[:200]}", 502)
        text = (r.json() or {}).get("text") or ""
        return jsonify({"ok": True, "text": text.strip()})

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

    @app.get("/api/home/now")
    @require_auth
    def home_now():
        """Что смотреть сейчас — слот времени + сценарий из своей библиотеки."""
        uid = current_user()["user_id"]
        slot = (request.args.get("slot") or "any").strip().lower()
        mood = (request.args.get("mood") or "").strip().lower()
        limit = min(12, max(3, int(request.args.get("limit") or 6)))
        data = now_plan.pick_now(uid, slot=slot, mood=mood, limit=limit)
        return jsonify({"ok": True, **data})

    @app.get("/api/home/digest")
    @require_auth
    def home_digest():
        uid = current_user()["user_id"]
        return jsonify({"ok": True, **now_plan.weekly_digest(uid)})

    @app.post("/api/home/digest/send")
    @require_auth
    def home_digest_send():
        """Push weekly digest to user's devices (if FCM configured)."""
        uid = current_user()["user_id"]
        prefs = now_plan.get_prefs(uid)
        if prefs.get("digest_enabled") is False:
            return jsonify({"ok": True, "sent": 0, "note": "Дайджест выключен в настройках"})
        dig = now_plan.weekly_digest(uid)
        try:
            result = push.send_to_user(
                uid,
                title=dig["title"],
                body=dig["body"],
                data={"type": "digest", "route": "/"},
            )
        except Exception as e:
            log.warning("digest push failed: %s", e)
            return json_error(f"Не удалось отправить: {e}", 502)
        return jsonify({"ok": True, "sent": int((result or {}).get("sent") or 0), "digest": dig, "push": result})

    @app.get("/api/prefs")
    @require_auth
    def get_user_prefs():
        uid = current_user()["user_id"]
        return jsonify(
            {
                "ok": True,
                "prefs": now_plan.get_prefs(uid),
                "daypart_themes": now_plan.daypart_theme_catalog(),
                "daypart": now_plan.current_daypart(now_plan.get_prefs(uid)),
            }
        )

    @app.post("/api/prefs")
    @require_auth
    def set_user_prefs():
        uid = current_user()["user_id"]
        body = request.get_json(silent=True) or {}
        prefs = now_plan.set_prefs(uid, body)
        return jsonify({"ok": True, "prefs": prefs})

    @app.post("/api/home/morning-push/send")
    @require_auth
    def morning_push_send():
        uid = current_user()["user_id"]
        try:
            result = digest_jobs.send_morning_for_user(uid)
        except Exception as e:
            log.warning("morning push failed: %s", e)
            return json_error(f"Не удалось отправить: {e}", 502)
        return jsonify({"ok": True, **result})

    @app.post("/api/videos/<video_id>/reclassify")
    @require_auth
    def reclassify_video(video_id: str):
        """«Не туда»: переложить в другую папку и запомнить keyword/channel rule."""
        uid = current_user()["user_id"]
        body = request.get_json(silent=True) or {}
        list_id = body.get("list_id")
        if not list_id:
            return json_error("Укажите list_id")
        list_id = int(list_id)
        lst = db.fetchone(
            "SELECT id, title FROM lists WHERE id = ? AND user_id = ?",
            (list_id, uid),
        )
        if not lst:
            return json_error("Папка не найдена", 404)
        row = db.fetchone("SELECT * FROM videos WHERE video_id = ?", (video_id,))
        if not row:
            return json_error("Нет видео", 404)
        # Remove from other theme-ish lists (keep YT: dumps and music hidden)
        theme_lists = db.fetchall(
            "SELECT id, title FROM lists WHERE user_id = ?", (uid,)
        )
        for t in theme_lists:
            title = (t.get("title") or "")
            if title.startswith("YT:") or "скрыто" in title.lower():
                continue
            if int(t["id"]) == list_id:
                continue
            db.execute(
                "DELETE FROM list_items WHERE list_id = ? AND video_id = ?",
                (int(t["id"]), video_id),
            )
        _add_to_list(uid, list_id, video_id)
        # Learn a light rule: channel or keyword from title
        organize.ensure_classify_tables()
        rule_type = (body.get("rule_type") or "").strip()
        rule_value = (body.get("rule_value") or "").strip()
        if not rule_type:
            ch = (row.get("channel_title") or "").strip()
            if ch:
                rule_type, rule_value = "channel", ch
            else:
                toks = [
                    t
                    for t in (row.get("title") or "").lower().replace(":", " ").split()
                    if len(t) >= 5
                ][:1]
                if toks:
                    rule_type, rule_value = "keyword", toks[0]
        if rule_type and rule_value:
            existing = db.fetchone(
                "SELECT id FROM classify_rules WHERE user_id = ? AND list_id = ? "
                "AND rule_type = ? AND rule_value = ?",
                (uid, list_id, rule_type, rule_value[:200]),
            )
            if not existing:
                db.execute(
                    "INSERT INTO classify_rules (user_id, list_id, rule_type, rule_value, priority) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (uid, list_id, rule_type[:40], rule_value[:200], 5),
                )
        return jsonify(
            {
                "ok": True,
                "list_id": list_id,
                "list_title": lst.get("title"),
                "learned": {"type": rule_type, "value": rule_value} if rule_type else None,
            }
        )

    @app.get("/api/home/plan")
    @require_auth
    def home_plan_get():
        uid = current_user()["user_id"]
        return jsonify({"ok": True, **now_plan.get_light_plan(uid)})

    @app.post("/api/home/plan")
    @require_auth
    def home_plan_set():
        uid = current_user()["user_id"]
        body = request.get_json(silent=True) or {}
        if body.get("video_id") and body.get("action") == "add":
            plan = now_plan.add_to_light_plan(
                uid, body.get("video_id"), bucket=(body.get("bucket") or "tonight")
            )
            return jsonify({"ok": True, **plan})
        if body.get("video_id") and body.get("action") == "remove":
            plan = now_plan.remove_from_light_plan(
                uid, body.get("video_id"), bucket=(body.get("bucket") or "tonight")
            )
            return jsonify({"ok": True, **plan})
        plan = now_plan.set_light_plan(
            uid,
            tonight=body.get("tonight"),
            week=body.get("week"),
        )
        return jsonify({"ok": True, **plan})

    @app.get("/api/onboarding/inbox")
    @require_auth
    def onboarding_inbox():
        uid = current_user()["user_id"]
        return jsonify({"ok": True, **now_plan.inbox_onboarding_status(uid)})

    @app.post("/api/onboarding/inbox/done")
    @require_auth
    def onboarding_inbox_done():
        uid = current_user()["user_id"]
        now_plan.set_prefs(uid, {"inbox_onboarding_done": True})
        return jsonify({"ok": True, **now_plan.inbox_onboarding_status(uid)})

    @app.post("/api/metrics/track")
    @require_auth
    def metrics_track():
        uid = current_user()["user_id"]
        body = request.get_json(silent=True) or {}
        r = metrics.track(
            uid,
            body.get("event_type") or "",
            video_id=body.get("video_id") or "",
            surface=body.get("surface") or "",
            meta=body.get("meta") if isinstance(body.get("meta"), dict) else None,
        )
        if not r.get("ok"):
            return json_error(r.get("error") or "bad event")
        return jsonify(r)

    @app.get("/api/metrics/summary")
    @require_auth
    def metrics_summary():
        uid = current_user()["user_id"]
        return jsonify({"ok": True, **metrics.weekly_summary(uid)})

    @app.get("/api/reminders")
    @require_auth
    def reminders_list():
        uid = current_user()["user_id"]
        return jsonify({"ok": True, "items": reminders_svc.list_reminders(uid)})

    @app.post("/api/reminders")
    @require_auth
    def reminders_create():
        uid = current_user()["user_id"]
        body = request.get_json(silent=True) or {}
        r = reminders_svc.set_reminder(uid, body.get("video_id") or "", body.get("remind_at") or "")
        if not r.get("ok"):
            return json_error(r.get("error") or "Не удалось")
        return jsonify(r)

    @app.post("/api/reminders/<int:reminder_id>/done")
    @require_auth
    def reminders_done(reminder_id: int):
        uid = current_user()["user_id"]
        return jsonify(reminders_svc.complete_reminder(uid, reminder_id))

    @app.delete("/api/reminders/<int:reminder_id>")
    @require_auth
    def reminders_delete(reminder_id: int):
        uid = current_user()["user_id"]
        return jsonify(reminders_svc.delete_reminder(uid, reminder_id))

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
                SELECT v.*, li.status, li.saved_at, li.watched_at, li.source, li.interest
                FROM library_items li JOIN videos v ON v.video_id = li.video_id
                WHERE li.user_id = ? AND li.status = 'queue'
                ORDER BY COALESCE(li.interest, 0) DESC, li.saved_at DESC LIMIT ?
                """,
                (uid, max(limit * 16, 200)),
            )
            pool = _clean_lib_rows(pool, allow_music=False)
            if offset == 0:
                # Pin manual adds + high interest at head
                pin_sources = {"android_share", "paste", "share", "add"}
                pinned = [
                    r for r in pool
                    if (r.get("source") or "").strip().lower() in pin_sources
                    or int(r.get("interest") or 0) >= 2
                ][: max(8, limit // 2)]
                pinned_ids = {r.get("video_id") for r in pinned}
                rest = [r for r in pool if r.get("video_id") not in pinned_ids]
                rows = (pinned + _diversify_lib_rows(rest, limit))[:limit]
            else:
                rows = pool[offset : offset + limit]
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
        for_home = (request.args.get("for_home") or "").strip() in ("1", "true", "yes")
        try:
            tag_id = int(request.args.get("tag_id") or 0)
        except ValueError:
            tag_id = 0
        if tag_id:
            rows = db.fetchall(
                """
                SELECT DISTINCT l.*
                FROM lists l
                JOIN list_items x ON x.list_id = l.id
                JOIN item_tags it ON it.video_id = x.video_id AND it.user_id = l.user_id
                WHERE l.user_id = ? AND it.tag_id = ?
                ORDER BY l.created_at DESC
                """,
                (uid, tag_id),
            )
        else:
            rows = db.fetchall(
                "SELECT * FROM lists WHERE user_id = ? ORDER BY COALESCE(sort_order, 1000) ASC, created_at DESC",
                (uid,),
            )
        out = []
        for r in rows:
            hidden = int(r.get("hidden_from_home") or 0) != 0
            if for_home and hidden:
                continue
            cnt = db.fetchone(
                "SELECT COUNT(*) AS c FROM list_items WHERE list_id = ?",
                (r["id"],)
            )
            covers = db.fetchall(
                """
                SELECT v.thumb_url, v.title, v.video_id
                FROM list_items x
                JOIN videos v ON v.video_id = x.video_id
                WHERE x.list_id = ?
                  AND COALESCE(v.thumb_url, '') != ''
                  AND lower(COALESCE(v.title, '')) NOT IN ('private video', 'deleted video', 'deleted video.')
                ORDER BY x.position ASC, x.added_at DESC
                LIMIT 3
                """,
                (r["id"],),
            )
            out.append(
                {
                    "id": r["id"],
                    "title": r["title"],
                    "created_at": str(r.get("created_at") or ""),
                    "count": int((cnt or {}).get("c") or 0),
                    "hidden_from_home": hidden,
                    "covers": [
                        {
                            "thumb_url": c.get("thumb_url") or yt.thumb_url(c["video_id"]),
                            "title": c.get("title") or "",
                        }
                        for c in covers
                    ],
                }
            )
        return jsonify({"ok": True, "lists": out})

    @app.patch("/api/lists/<int:list_id>")
    @require_auth
    def patch_list(list_id: int):
        uid = current_user()["user_id"]
        lst = db.fetchone(
            "SELECT * FROM lists WHERE id = ? AND user_id = ?",
            (list_id, uid),
        )
        if not lst:
            return json_error("Список не найден", 404)
        body = request.get_json(silent=True) or {}
        if "title" in body:
            title = (body.get("title") or "").strip()[:120]
            if title:
                db.execute(
                    "UPDATE lists SET title = ? WHERE id = ? AND user_id = ?",
                    (title, list_id, uid),
                )
        if "hidden_from_home" in body:
            hidden = 1 if body.get("hidden_from_home") in (True, 1, "1", "true", "yes") else 0
            db.execute(
                "UPDATE lists SET hidden_from_home = ? WHERE id = ? AND user_id = ?",
                (hidden, list_id, uid),
            )
        row = db.fetchone(
            "SELECT * FROM lists WHERE id = ? AND user_id = ?",
            (list_id, uid),
        )
        return jsonify(
            {
                "ok": True,
                "list": {
                    "id": row["id"],
                    "title": row.get("title"),
                    "hidden_from_home": int(row.get("hidden_from_home") or 0) != 0,
                },
            }
        )

    @app.delete("/api/lists/<int:list_id>")
    @require_auth
    def delete_list(list_id: int):
        uid = current_user()["user_id"]
        lst = db.fetchone(
            "SELECT id FROM lists WHERE id = ? AND user_id = ?",
            (list_id, uid),
        )
        if not lst:
            return json_error("Список не найден", 404)
        db.execute("DELETE FROM list_items WHERE list_id = ?", (list_id,))
        db.execute("DELETE FROM lists WHERE id = ? AND user_id = ?", (list_id, uid))
        return jsonify({"ok": True})

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
        cards = []
        for r in rows:
            tags = db.fetchall(
                """
                SELECT t.id, t.name, t.emoji, t.color
                FROM item_tags it
                JOIN user_tags t ON t.id = it.tag_id
                WHERE it.user_id = ? AND it.video_id = ?
                """,
                (uid, r["video_id"]),
            )
            cards.append(
                yt.card_from_video_row(
                    r,
                    {
                        "status": r.get("status"),
                        "saved_at": str(r.get("saved_at") or ""),
                        "user_tags": tags,
                    },
                )
            )
        return jsonify(
            {
                "ok": True,
                "list": {"id": lst["id"], "title": lst["title"]},
                "items": cards,
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

    @app.delete("/api/lists/<int:list_id>/items/<video_id>")
    @require_auth
    def list_remove_item(list_id: int, video_id: str):
        uid = current_user()["user_id"]
        lst = db.fetchone(
            "SELECT id FROM lists WHERE id = ? AND user_id = ?",
            (list_id, uid),
        )
        if not lst:
            return json_error("Список не найден", 404)
        db.execute(
            "DELETE FROM list_items WHERE list_id = ? AND video_id = ?",
            (list_id, video_id),
        )
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
        ("история", "🏛"),
        ("наука", "🔬"),
        ("технологии", "💻"),
        ("бизнес", "💼"),
        ("психология", "🧠"),
        ("путешествия", "✈️"),
        ("дизайн", "🎨"),
        ("политика", "🏛"),
        ("здоровье", "💚"),
        ("авто", "🚗"),
        ("языки", "🗣"),
        ("искусство", "🖼"),
        ("экономика", "📈"),
        ("программирование", "⌨️"),
        ("мода", "👗"),
    ]

    @app.get("/api/tags")
    @require_auth
    def get_tags():
        uid = current_user()["user_id"]
        only_used = (request.args.get("used") or "1") != "0"
        rows = db.fetchall(
            """
            SELECT t.id, t.name, t.emoji, t.color,
                   COUNT(it.video_id) AS video_count
            FROM user_tags t
            LEFT JOIN item_tags it
              ON it.tag_id = t.id AND it.user_id = t.user_id
            WHERE t.user_id = ?
            GROUP BY t.id, t.name, t.emoji, t.color
            ORDER BY t.name
            """,
            (uid,),
        )
        tags = []
        for r in rows:
            n = int(r.get("video_count") or 0)
            if only_used and n <= 0:
                continue
            tags.append(
                {
                    "id": r["id"],
                    "name": r.get("name"),
                    "emoji": r.get("emoji"),
                    "color": r.get("color"),
                    "video_count": n,
                }
            )
        return jsonify({"ok": True, "tags": tags, "llm": llm.available()})

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

    @app.get("/api/auth/android/done")
    def auth_android_bridge():
        """HTTPS bridge for Custom Tabs → native Clip Queue app."""
        return send_from_directory(WEB, "android-auth.html")

    @app.get("/")
    @app.get("/home")
    @app.get("/queue")
    @app.get("/channels")
    @app.get("/lists")
    @app.get("/tags")
    @app.get("/add")
    @app.get("/organize")
    @app.get("/search")
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

    try:
        metrics.ensure_tables()
        digest_jobs.start_background()
    except Exception as e:
        log.warning("startup background: %s", e)

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.environ.get("PORT") or 8765)
    app.run(host="0.0.0.0", port=port, debug=True)
