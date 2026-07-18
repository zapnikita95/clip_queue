#!/usr/bin/env python3
from backend import db, organize


def main() -> None:
    uid = int(
        db.fetchone(
            "SELECT user_id FROM library_items GROUP BY user_id ORDER BY COUNT(*) DESC LIMIT 1"
        )["user_id"]
    )
    p = organize.propose_structure(uid, use_llm=False)
    print("summary:", p.get("summary"))
    print("--- folders ---")
    for f in p.get("folders") or []:
        rule = f.get("rule") or {}
        kind = rule.get("type") or "draft"
        print(f"{kind:10} | {f['count']:3} | {f['title']}")
    themes = [f for f in p["folders"] if (f.get("rule") or {}).get("type") == "theme"]
    assert themes, "expected theme folders"
    titles = {f["title"] for f in themes}
    print("theme titles:", sorted(titles))
    for want in ("Про английский", "Новости"):
        if want in titles:
            print("OK has", want)


if __name__ == "__main__":
    main()
