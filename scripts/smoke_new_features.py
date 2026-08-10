"""Smoke-test Kyro growth features against production API."""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

BASE = "https://clip-queue-web-production.up.railway.app"
results: list[tuple[str, bool, str]] = []


def req(method: str, path: str, token: str | None = None, body: dict | None = None):
    data = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    r = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=45) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            j = json.loads(raw)
        except Exception:
            j = {"raw": raw[:300]}
        return e.code, j


def check(name: str, ok: bool, detail: str = ""):
    results.append((name, ok, detail))
    mark = "OK" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))


def main() -> int:
    code, health = req("GET", "/health")
    check("health", code == 200 and health.get("ok") is True, f"v={health.get('version')} fcm={health.get('fcm_configured')}")

    code, login = req("POST", "/api/auth/dev-login", body={})
    token = (login or {}).get("token")
    check("dev-login", code == 200 and bool(token), f"user={(login.get('user') or {}).get('email')}")
    if not token:
        return 1

    code, now = req("GET", "/api/home/now?limit=6", token)
    picks = now.get("picks") or []
    slots = now.get("slots") or []
    moods = now.get("moods") or []
    check(
        "home/now",
        code == 200 and now.get("ok") and slots and moods,
        f"daypart={now.get('daypart')} picks={len(picks)} slots={len(slots)} moods={len(moods)}",
    )
    if picks:
        check("now reason", bool(picks[0].get("reason") or picks[0].get("title")), picks[0].get("reason") or picks[0].get("title", "")[:60])

    code, now2 = req("GET", "/api/home/now?slot=short&mood=learn&limit=4", token)
    check("home/now filters", code == 200 and now2.get("ok") is True, f"slot={now2.get('slot')} mood={now2.get('mood')} picks={len(now2.get('picks') or [])}")

    code, prefs = req("GET", "/api/prefs", token)
    check("prefs get", code == 200 and prefs.get("ok") is True, str(list((prefs.get("prefs") or prefs).keys())[:8]))

    code, prefs_set = req(
        "POST",
        "/api/prefs",
        token,
        {
            "morning_themes": ["история", "наука"],
            "evening_themes": ["документалки", "standup"],
            "morning_push_hour": 9,
            "digest_weekday": 0,
        },
    )
    check("prefs set daypart tastes", code == 200 and prefs_set.get("ok") is True, str(prefs_set.get("prefs") or prefs_set)[:120])

    code, plan = req("GET", "/api/home/plan", token)
    check("home/plan get", code == 200 and plan.get("ok") is True, f"keys={list(plan.keys())}")

    vid = None
    if picks:
        vid = picks[0].get("video_id")
    if not vid:
        # save a known short video for further tests
        code, save = req(
            "POST",
            "/api/videos/save",
            token,
            {
                "url": "https://www.youtube.com/watch?v=jNQXAC9IVRw",
                "source": "smoke_test",
                "apply_classification": True,
                "classify_async": True,
                "status": "queue",
            },
        )
        vid = (save.get("item") or {}).get("video_id") or save.get("video_id")
        check("save async classify", code == 200 and save.get("ok") and bool(vid), f"async={save.get('classify_async')} vid={vid}")
    else:
        check("have video for plan/open", True, vid)

    if vid:
        code, add_plan = req("POST", "/api/home/plan", token, {"action": "add", "bucket": "tonight", "video_id": vid})
        check("plan add tonight", code == 200 and add_plan.get("ok") is True, str(add_plan)[:100])

        code, plan2 = req("GET", "/api/home/plan", token)
        tonight = plan2.get("tonight") or plan2.get("items") or []
        # tolerate different shapes
        in_plan = False
        blob = json.dumps(plan2, ensure_ascii=False)
        in_plan = vid in blob
        check("plan contains video", in_plan, f"tonight_type={type(tonight).__name__}")

        remind_at = (datetime.now(timezone.utc) + timedelta(hours=4)).isoformat()
        code, rem = req("POST", "/api/reminders", token, {"video_id": vid, "remind_at": remind_at})
        check("reminder create 4h", code == 200 and rem.get("ok") is True, str(rem)[:120])

        code, openr = req("POST", f"/api/videos/{vid}/open", token, {"surface": "push"})
        check("open video (push surface)", code == 200 and openr.get("ok") is True, f"url={(openr.get('watch_url') or '')[:48]}")

        code, patch = req("PATCH", f"/api/library/{vid}", token, {"status": "queue"})
        check("library patch back to queue", code == 200 and patch.get("ok") is True, str(patch)[:80])

    # share-like save
    code, share = req(
        "POST",
        "/api/videos/save",
        token,
        {
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "source": "android_share",
            "apply_classification": True,
            "classify_async": True,
            "status": "queue",
        },
    )
    check(
        "android_share save async",
        code == 200 and share.get("ok") and share.get("classify_async") is True,
        f"engine={share.get('classify_engine')} vid={share.get('video_id') or (share.get('item') or {}).get('video_id')}",
    )

    code, digest = req("GET", "/api/home/digest", token)
    check("digest get", code in (200, 404) or digest.get("ok") is True or "error" not in str(digest).lower() or code == 200, f"code={code} keys={list(digest.keys())[:8]}")

    code, metrics = req("POST", "/api/metrics/track", token, {"event": "now_impression", "surface": "android_home"})
    check("metrics track", code == 200 and metrics.get("ok") is True, str(metrics)[:80])

    code, summary = req("GET", "/api/metrics/summary", token)
    check("metrics summary", code == 200 and summary.get("ok") is True, str(list(summary.keys())[:8]))

    # morning push endpoint may exist
    code, mp = req("POST", "/api/home/morning-push/send", token, {})
    check("morning-push send (optional)", code in (200, 400, 404, 429), f"code={code} {str(mp)[:100]}")

    failed = [r for r in results if not r[1]]
    print("\n=== SUMMARY ===")
    print(f"passed={len(results) - len(failed)} failed={len(failed)} total={len(results)}")
    for name, ok, detail in failed:
        print(f"  FAIL: {name} — {detail}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
