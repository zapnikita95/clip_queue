#!/usr/bin/env bash
set -euo pipefail
BASE="${1:-http://127.0.0.1:8765}"

echo "== health =="
curl -sf "$BASE/health" | head -c 400
echo

echo "== dev login =="
TOKEN=$(curl -sf -X POST "$BASE/api/auth/dev-login" -H 'Content-Type: application/json' -d '{}' | python3 -c 'import sys,json; print(json.load(sys.stdin)["token"])')
AUTH="Authorization: Bearer $TOKEN"

echo "== save sample =="
curl -sf -X POST "$BASE/api/videos/save" -H "$AUTH" -H 'Content-Type: application/json' \
  -d '{"url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","source":"smoke"}' | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d["ok"], d["item"]["title"][:60])'

echo "== home shell =="
curl -sf "$BASE/api/home/shell" -H "$AUTH" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d["counts"])'

echo "== rail queue =="
curl -sf "$BASE/api/home/rails/queue?limit=3" -H "$AUTH" | python3 -c 'import sys,json; d=json.load(sys.stdin); print(len(d.get("items") or []), "items")'

echo "OK"