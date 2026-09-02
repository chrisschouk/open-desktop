#!/usr/bin/env bash
# Golden-path demo: Music PR discovery via OpenWorker API
set -euo pipefail

API="${OPENDESKTOP_API_URL:-http://localhost:8000}"
PROMPT="${1:-Find 10 UK indie radio pluggers and playlist curators for an upcoming rock release}"

echo "==> Health"
curl -sf "$API/api/v1/health" | python3 -m json.tool

echo ""
echo "==> Create session"
SESSION_JSON=$(curl -sf -X POST "$API/api/v1/sessions" \
  -H "Content-Type: application/json" \
  -d '{"persona_id":"openworker"}')
SESSION_ID=$(echo "$SESSION_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['session']['id'])")
echo "Session: $SESSION_ID"

echo ""
echo "==> Send music PR prompt"
CHAT_JSON=$(PROMPT="$PROMPT" SESSION_ID="$SESSION_ID" python3 <<'PY'
import json
import os
import urllib.request

api = os.environ.get("OPENDESKTOP_API_URL", "http://localhost:8000").rstrip("/")
body = json.dumps({
    "message": os.environ["PROMPT"],
    "session_id": os.environ["SESSION_ID"],
}).encode()
req = urllib.request.Request(
    f"{api}/api/v1/chat",
    data=body,
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req) as resp:
    print(resp.read().decode())
PY
)
echo "$CHAT_JSON" | python3 -m json.tool

echo ""
echo "==> Poll until idle (max 5 min)"
for i in $(seq 1 60); do
  DETAIL=$(curl -sf "$API/api/v1/sessions/$SESSION_ID")
  STATUS=$(echo "$DETAIL" | python3 -c "import sys,json; print(json.load(sys.stdin)['session']['status'])")
  echo "  [$i] session status: $STATUS"
  if [ "$STATUS" = "idle" ] || [ "$STATUS" = "error" ]; then
    echo "$DETAIL" | python3 -m json.tool
    exit 0
  fi
  sleep 5
done

echo "Timed out waiting for session to finish"
exit 1
