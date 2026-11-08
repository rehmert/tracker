#!/usr/bin/env bash
# Release 498: isolated, offline browser qualification for a candidate worktree.
# Only localhost; never reads /etc/tracker.env or the installed Tracker database.
set -Eeuo pipefail
umask 077

[[ $# == 2 ]] || { echo "Usage: tracker-browser-qualify.sh SOURCE PYTHON" >&2; exit 2; }
SOURCE="$(cd "$1" && pwd -P)"
PY="$2"
[[ "$SOURCE" != /opt/tracker && -f "$SOURCE/app/main.py" && -x "$PY" ]] || {
  echo "ERROR: Source must be a separate candidate worktree and Python must exist" >&2
  exit 2
}
ROOT="$(mktemp -d /tmp/tracker-browser-qa.XXXXXXXX)"
DATA="$ROOT/data"
mkdir -m 700 "$DATA"
SERVER_LOG="$ROOT/server.log"
SERVER_PID=""

cleanup() {
  local code=$?
  trap - EXIT
  if [[ -n "$SERVER_PID" ]]; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
  echo "ISOLATED_SERVER_STOPPED=YES"
  if ((code != 0)); then
    echo "ISOLATED_BROWSER=FAILED code=$code"
    echo "SERVER_LOG=$SERVER_LOG"
    tail -n 50 "$SERVER_LOG" 2>/dev/null || true
  else
    echo "ISOLATED_BROWSER=PASSED"
  fi
  exit "$code"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

cd "$SOURCE"
PORT="$("$PY" - <<'PY'
import socket
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
)"
URL="http://127.0.0.1:$PORT"

echo "=== ISOLATED CANDIDATE SERVER ==="
echo "CANDIDATE_COMMIT=$(git rev-parse HEAD)"
echo "CANDIDATE_URL=$URL"

env -i HOME=/root PATH=/usr/local/bin:/usr/bin:/bin \
  PYTHONPATH="$SOURCE" TRACKER_DATA_DIR="$DATA" TRACKER_INSTANCE=DEV \
  PYTHONDONTWRITEBYTECODE=1 \
  "$PY" -B -m uvicorn app.main:app --host 127.0.0.1 \
    --port "$PORT" --app-dir "$SOURCE" > "$SERVER_LOG" 2>&1 &
SERVER_PID=$!

"$PY" - "$URL" "$SERVER_PID" <<'PY'
import os
import sys
import time
import urllib.error
import urllib.request

url, pid = sys.argv[1], int(sys.argv[2])
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
for _ in range(60):
    try:
        os.kill(pid, 0)
        with opener.open(url + "/healthz", timeout=2) as response:
            if response.status != 200 or b'"ok":true' not in response.read().replace(b' ', b''):
                raise RuntimeError("Unexpected candidate health response")
        with opener.open(url + "/", timeout=5) as response:
            html = response.read()
            if response.status == 200 and b'id="nav-sortable"' in html:
                print("ISOLATED_SERVER_READY=YES")
                break
    except (OSError, urllib.error.URLError, RuntimeError):
        time.sleep(0.5)
else:
    raise SystemExit("ERROR: Isolated candidate did not become ready")
PY

echo "=== OFFLINE FOOD AND LABS BROWSER TESTS + LIVE NAVIGATION ==="
env -i HOME=/root PATH=/usr/local/bin:/usr/bin:/bin \
  PYTHONPATH="$SOURCE" TRACKER_DATA_DIR="$DATA" \
  TRACKER_TEST_URL="$URL" PYTHONDONTWRITEBYTECODE=1 \
  "$PY" -B -m pytest -q -x --tb=short \
    tests/browser/test_food_search_ui.py \
    tests/browser/test_labs_overview.py \
    tests/browser/test_navigation.py
