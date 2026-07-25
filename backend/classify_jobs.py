"""Background «Разобрать» jobs — progress without Railway 502 on long HTTP."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from typing import Any, Optional

from backend import organize

log = logging.getLogger("clip_queue.classify")

_LOCK = threading.Lock()
_JOBS: dict[str, dict[str, Any]] = {}
_USER_ACTIVE: dict[int, str] = {}


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
        if job.get("status") in ("done", "error") and time.time() - float(job.get("updated_at") or 0) > 120:
            _USER_ACTIVE.pop(user_id, None)
            return None
        return dict(job)


def _set(job_id: str, **fields: Any) -> None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return
        job.update(fields)
        job["updated_at"] = time.time()


def start_classify(user_id: int, *, limit: int = 200, use_llm: bool = True) -> dict[str, Any]:
    with _LOCK:
        existing_id = _USER_ACTIVE.get(user_id)
        if existing_id:
            ex = _JOBS.get(existing_id)
            if ex and ex.get("status") == "running":
                return dict(ex)

        job_id = uuid.uuid4().hex[:12]
        job = {
            "id": job_id,
            "user_id": user_id,
            "status": "running",
            "pct": 2,
            "title": "Готовлю разбор",
            "detail": "Считаю новые видео…",
            "classified": 0,
            "total": 0,
            "skipped": 0,
            "error": None,
            "created_at": time.time(),
            "updated_at": time.time(),
        }
        _JOBS[job_id] = job
        _USER_ACTIVE[user_id] = job_id

    def run() -> None:
        try:
            def on_progress(ev: dict) -> None:
                _set(
                    job_id,
                    pct=ev.get("pct") or 0,
                    title=ev.get("title") or "Разбираю",
                    detail=ev.get("detail") or "",
                    classified=ev.get("classified") or 0,
                    total=ev.get("total") or 0,
                    eta_sec=ev.get("eta_sec"),
                    elapsed_sec=ev.get("elapsed_sec"),
                )

            result = organize.classify_pending_batch(
                user_id,
                limit=limit,
                use_llm=use_llm,
                progress_cb=on_progress,
            )
            _set(
                job_id,
                status="done",
                pct=100,
                title="Готово",
                detail=(
                    f"В папки: {result.get('classified', 0)} из {result.get('total', 0)}"
                    + (
                        f" · осталось {result.get('pending_left')}"
                        if result.get("pending_left")
                        else ""
                    )
                ),
                classified=result.get("classified") or 0,
                total=result.get("total") or 0,
                skipped=result.get("skipped") or 0,
                pending_left=result.get("pending_left") or 0,
                result=result,
            )
        except Exception as e:
            log.exception("classify job failed")
            _set(
                job_id,
                status="error",
                pct=100,
                title="Ошибка",
                detail=str(e)[:240],
                error=str(e)[:240],
            )

    threading.Thread(target=run, name=f"classify-{job_id}", daemon=True).start()
    with _LOCK:
        return dict(_JOBS[job_id])
