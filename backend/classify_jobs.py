"""Background «Разобрать» jobs with disk checkpoint + resume after 502/redeploy."""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from typing import Any, Optional

from backend import organize
from backend.paths import data_dir

log = logging.getLogger("clip_queue.classify")

_LOCK = threading.Lock()
_JOBS: dict[str, dict[str, Any]] = {}
_USER_ACTIVE: dict[int, str] = {}


def _jobs_path():
    return data_dir() / "classify_jobs.json"


def _persist() -> None:
    try:
        payload = {
            "jobs": _JOBS,
            "user_active": {str(k): v for k, v in _USER_ACTIVE.items()},
        }
        _jobs_path().write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        log.warning("classify job persist failed: %s", e)


def _restore() -> None:
    path = _jobs_path()
    if not path.exists():
        return
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        jobs = raw.get("jobs") or {}
        now = time.time()
        for jid, job in list(jobs.items()):
            if job.get("status") == "running" and now - float(job.get("updated_at") or 0) > 45:
                done_n = len(job.get("done_ids") or [])
                job["status"] = "paused"
                job["resumable"] = True
                job["title"] = "Разбор прерван"
                job["detail"] = (
                    f"Сохранено {done_n} из {job.get('total') or '?'} — можно продолжить"
                )
                job["error"] = None
            _JOBS[jid] = job
        for k, v in (raw.get("user_active") or {}).items():
            try:
                _USER_ACTIVE[int(k)] = v
            except Exception:
                pass
        _persist()
    except Exception as e:
        log.warning("classify job restore failed: %s", e)


_restore()


def _public(job: dict[str, Any]) -> dict[str, Any]:
    out = dict(job)
    done_ids = out.get("done_ids") or []
    out["done"] = int(out.get("done") or len(done_ids))
    out["done_ids_count"] = len(done_ids)
    out.pop("done_ids", None)
    return out


def get_job(job_id: str) -> Optional[dict[str, Any]]:
    with _LOCK:
        job = _JOBS.get(job_id)
        return _public(job) if job else None


def get_job_raw(job_id: str) -> Optional[dict[str, Any]]:
    with _LOCK:
        job = _JOBS.get(job_id)
        return dict(job) if job else None


def active_job_for_user(user_id: int) -> Optional[dict[str, Any]]:
    with _LOCK:
        jid = _USER_ACTIVE.get(user_id)
        job = _JOBS.get(jid) if jid else None
        if not job or int(job.get("user_id") or 0) != user_id:
            candidates = [
                j
                for j in _JOBS.values()
                if int(j.get("user_id") or 0) == user_id
                and j.get("status") in ("running", "paused")
            ]
            if not candidates:
                return None
            job = max(candidates, key=lambda j: float(j.get("updated_at") or 0))
        if job.get("status") == "done" and time.time() - float(job.get("updated_at") or 0) > 180:
            return None
        return _public(job)


def _set(job_id: str, **fields: Any) -> None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return
        job.update(fields)
        job["updated_at"] = time.time()
        _persist()


def _append_done(job_id: str, video_id: str, *, classified: bool) -> None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return
        ids = list(job.get("done_ids") or [])
        if video_id in ids:
            job["updated_at"] = time.time()
            _persist()
            return
        ids.append(video_id)
        job["done_ids"] = ids
        job["done"] = len(ids)
        if classified:
            job["classified"] = int(job.get("classified") or 0) + 1
        else:
            job["skipped"] = int(job.get("skipped") or 0) + 1
        job["updated_at"] = time.time()
        _persist()


def _find_resumable(user_id: int) -> Optional[dict[str, Any]]:
    paused = [
        j
        for j in _JOBS.values()
        if int(j.get("user_id") or 0) == user_id
        and j.get("status") in ("paused", "error")
        and j.get("resumable", j.get("status") == "paused")
        and (j.get("done_ids") or j.get("done"))
    ]
    if not paused:
        return None
    return max(paused, key=lambda j: float(j.get("updated_at") or 0))


def start_classify(
    user_id: int,
    *,
    limit: int = 200,
    use_llm: bool = True,
    resume: bool = False,
) -> dict[str, Any]:
    with _LOCK:
        # Reuse live running job
        jid = _USER_ACTIVE.get(user_id)
        if jid and jid in _JOBS and _JOBS[jid].get("status") == "running":
            return _public(_JOBS[jid])

        job: dict[str, Any] | None = None
        if resume:
            cand = None
            if jid and jid in _JOBS:
                ex = _JOBS[jid]
                if ex.get("status") in ("paused", "error") and ex.get("resumable", True):
                    cand = ex
            if not cand:
                cand = _find_resumable(user_id)
            if cand:
                job = cand
                job["status"] = "running"
                job["resumable"] = True
                job["title"] = "Продолжаю разбор"
                job["detail"] = (
                    f"С чекпоинта · уже {len(job.get('done_ids') or [])}"
                    f" из {job.get('total') or '?'}"
                )
                job["error"] = None
                job["updated_at"] = time.time()
                _USER_ACTIVE[user_id] = job["id"]
                _JOBS[job["id"]] = job
                _persist()

        if not job:
            job_id = uuid.uuid4().hex[:12]
            job = {
                "id": job_id,
                "user_id": user_id,
                "status": "running",
                "resumable": True,
                "pct": 2,
                "title": "Готовлю разбор",
                "detail": "Считаю новые видео…",
                "classified": 0,
                "skipped": 0,
                "done": 0,
                "total": 0,
                "done_ids": [],
                "limit": limit,
                "use_llm": use_llm,
                "error": None,
                "created_at": time.time(),
                "updated_at": time.time(),
            }
            _JOBS[job_id] = job
            _USER_ACTIVE[user_id] = job_id
            _persist()

        job_id = job["id"]

    def run() -> None:
        raw = get_job_raw(job_id) or {}
        skip = set(raw.get("done_ids") or [])
        lim = int(raw.get("limit") or limit)
        llm = bool(raw.get("use_llm") if "use_llm" in raw else use_llm)

        try:
            def on_progress(ev: dict) -> None:
                vid = (ev.get("video_id") or "").strip()
                if vid:
                    _append_done(job_id, vid, classified=bool(ev.get("was_classified")))
                _set(
                    job_id,
                    pct=ev.get("pct") or 0,
                    title=ev.get("title") or "Разбираю",
                    detail=ev.get("detail") or "",
                    total=ev.get("total") or 0,
                    eta_sec=ev.get("eta_sec"),
                    elapsed_sec=ev.get("elapsed_sec"),
                )

            result = organize.classify_pending_batch(
                user_id,
                limit=lim,
                use_llm=llm,
                skip_ids=skip,
                progress_cb=on_progress,
            )
            raw2 = get_job_raw(job_id) or {}
            _set(
                job_id,
                status="done",
                pct=100,
                resumable=False,
                title="Готово",
                detail=(
                    f"В папки: {raw2.get('classified') or 0}"
                    f" · пропущено: {raw2.get('skipped') or 0}"
                    + (
                        f" · ещё в очереди {result.get('pending_left')}"
                        if result.get("pending_left")
                        else ""
                    )
                ),
                total=result.get("total") or raw2.get("total") or 0,
                pending_left=result.get("pending_left") or 0,
            )
        except Exception as e:
            log.exception("classify job failed")
            raw2 = get_job_raw(job_id) or {}
            done_n = len(raw2.get("done_ids") or [])
            _set(
                job_id,
                status="paused",
                resumable=True,
                pct=min(99, int(raw2.get("pct") or 0) or 5),
                title="Разбор прерван",
                detail=(
                    f"Сохранено {done_n} из {raw2.get('total') or '?'} — нажми «Продолжить». "
                    f"({str(e)[:100]})"
                ),
                error=str(e)[:240],
            )

    threading.Thread(target=run, name=f"classify-{job_id}", daemon=True).start()
    return get_job(job_id) or {"id": job_id, "status": "running"}
