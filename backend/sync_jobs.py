"""Background YouTube sync jobs — avoid Railway 502 on long HTTP streams."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Any, Optional

from backend import yt_sync

log = logging.getLogger("clip_queue.sync")

_LOCK = threading.Lock()
_JOBS: dict[str, dict[str, Any]] = {}
_USER_ACTIVE: dict[int, str] = {}


def _set(job_id: str, **fields: Any) -> None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return
        job.update(fields)
        job["updated_at"] = time.time()


def get_job(job_id: str) -> Optional[dict[str, Any]]:
    with _LOCK:
        job = _JOBS.get(job_id)
        return dict(job) if job else None


def active_job_for_user(user_id: int) -> Optional[dict[str, Any]]:
    with _LOCK:
        jid = _USER_ACTIVE.get(user_id)
        if not jid:
            return None
        job = _JOBS.get(jid)
        if not job:
            return None
        if job.get("status") in ("done", "error") and time.time() - job.get("updated_at", 0) > 120:
            return None
        return dict(job)


def start_youtube_sync(user_id: int) -> dict[str, Any]:
    existing = active_job_for_user(user_id)
    if existing and existing.get("status") == "running":
        log.info("reuse running sync job user=%s job=%s", user_id, existing.get("id"))
        return existing

    job_id = uuid.uuid4().hex[:16]
    job = {
        "id": job_id,
        "user_id": user_id,
        "status": "running",
        "type": "progress",
        "pct": 1,
        "title": "Стартую синк",
        "detail": "Фоновая задача запущена",
        "elapsed_sec": 0,
        "eta_sec": None,
        "stats": None,
        "error": None,
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    with _LOCK:
        _JOBS[job_id] = job
        _USER_ACTIVE[user_id] = job_id

    def worker() -> None:
        t0 = time.time()
        log.info("sync start user=%s job=%s", user_id, job_id)
        try:
            for ev in yt_sync.iter_sync_youtube_library(user_id):
                elapsed = int(time.time() - t0)
                if ev.get("type") == "done":
                    _set(
                        job_id,
                        status="done",
                        type="done",
                        pct=100,
                        title=ev.get("title") or "Синк готов",
                        detail=ev.get("detail") or "",
                        elapsed_sec=ev.get("elapsed_sec", elapsed),
                        eta_sec=0,
                        stats=ev.get("stats"),
                        error=None,
                    )
                    log.info(
                        "sync done user=%s job=%s stats=%s",
                        user_id,
                        job_id,
                        ev.get("stats"),
                    )
                elif ev.get("type") == "error":
                    _set(
                        job_id,
                        status="error",
                        type="error",
                        title=ev.get("title") or "Ошибка",
                        detail=ev.get("error") or "",
                        error=ev.get("error"),
                        elapsed_sec=elapsed,
                    )
                    log.error("sync error event user=%s job=%s err=%s", user_id, job_id, ev.get("error"))
                else:
                    _set(
                        job_id,
                        status="running",
                        type="progress",
                        pct=ev.get("pct", 0),
                        title=ev.get("title") or "Синк",
                        detail=ev.get("detail") or "",
                        elapsed_sec=ev.get("elapsed_sec", elapsed),
                        eta_sec=ev.get("eta_sec"),
                    )
                    log.info(
                        "sync step user=%s job=%s pct=%s title=%s detail=%s",
                        user_id,
                        job_id,
                        ev.get("pct"),
                        ev.get("title"),
                        ev.get("detail"),
                    )
        except Exception as e:
            log.exception("sync failed user=%s job=%s", user_id, job_id)
            _set(
                job_id,
                status="error",
                type="error",
                title="Синк оборвался",
                detail=str(e)[:500],
                error=str(e)[:500],
                elapsed_sec=int(time.time() - t0),
            )

    threading.Thread(target=worker, name=f"yt-sync-{job_id}", daemon=True).start()
    return dict(job)
