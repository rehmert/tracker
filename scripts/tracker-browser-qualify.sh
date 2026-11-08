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
# HTMX is intentionally gitignored and absent from detached worktrees.
# Use only the already-installed local vendor asset, never download code
# or read application credentials/configuration.
VENDOR_SRC="/opt/tracker/app/static/vendor/htmx.min.js"
VENDOR_DST="$SOURCE/app/static/vendor/htmx.min.js"
[[ -f "$VENDOR_SRC" && ! -L "$VENDOR_SRC" && ! -e "$VENDOR_DST" ]] || {
  echo "ERROR: Clean installed HTMX vendor asset required for isolated browser QA" >&2
  exit 2
}
mkdir -p "$(dirname "$VENDOR_DST")"
install -m 0644 "$VENDOR_SRC" "$VENDOR_DST"
cmp -s "$VENDOR_SRC" "$VENDOR_DST" || {
  echo "ERROR: Copied isolated HTMX asset differs from installed source" >&2
  exit 2
}
echo "ISOLATED_HTMX_VENDOR=VERIFIED"
ROOT="$(mktemp -d /tmp/tracker-browser-qa.XXXXXXXX)"
DATA="$ROOT/data"
mkdir -m 700 "$DATA"
SERVER_LOG="$ROOT/server.log"
TLS_LOG="$ROOT/tls-proxy.log"
TEST_LOG="$ROOT/pytest-browser.log"
SERVER_PID=""
TLS_PID=""

cleanup() {
  local code=$?
  trap - EXIT
  if [[ -n "$TLS_PID" ]]; then
    kill "$TLS_PID" 2>/dev/null || true
    wait "$TLS_PID" 2>/dev/null || true
  fi
  if [[ -n "$SERVER_PID" ]]; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
  echo "ISOLATED_SERVER_STOPPED=YES"
  if ((code != 0)); then
    echo "ISOLATED_BROWSER=FAILED code=$code"
    echo "BROWSER_TEST_LOG=$TEST_LOG"
    if [[ -f "$TEST_LOG" ]]; then
      echo "=== BROWSER FAILURE SUMMARY ==="
      grep -E '^(FAILED |ERROR |E   |[0-9]+ failed|[0-9]+ error)' "$TEST_LOG" | tail -n 35 || true
    fi
    echo "SERVER_LOG=$SERVER_LOG"
    tail -n 15 "$SERVER_LOG" 2>/dev/null || true
    echo "TLS_LOG=$TLS_LOG"
    tail -n 10 "$TLS_LOG" 2>/dev/null || true
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

echo "=== ISOLATED HTTPS REVERSE PROXY ==="
command -v openssl >/dev/null || {
  echo "ERROR: openssl is required for local HTTPS QA" >&2
  exit 2
}
HTTPS_PORT="$("$PY" - <<'PY'
import socket
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
)"
HTTPS_URL="https://127.0.0.1:$HTTPS_PORT"
openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
  -subj '/CN=127.0.0.1' \
  -addext 'subjectAltName=IP:127.0.0.1' \
  -keyout "$ROOT/qa-private-key.pem" -out "$ROOT/qa-cert.pem" \
  >"$ROOT/openssl.log" 2>&1
env -i HOME=/root PATH=/usr/local/bin:/usr/bin:/bin \
  PYTHONDONTWRITEBYTECODE=1 \
  "$PY" -B scripts/tracker-tls-proxy501.py \
  --listen-port "$HTTPS_PORT" --backend-port "$PORT" \
  --cert "$ROOT/qa-cert.pem" --key "$ROOT/qa-private-key.pem" \
  >"$TLS_LOG" 2>&1 &
TLS_PID=$!

"$PY" - "$HTTPS_URL" "$TLS_PID" <<'PY'
import os
import ssl
import sys
import time
import urllib.error
import urllib.request

url, pid = sys.argv[1], int(sys.argv[2])
context = ssl._create_unverified_context()  # Ephemeral test-only certificate.
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
    urllib.request.HTTPSHandler(context=context))
for _ in range(60):
    try:
        os.kill(pid, 0)
        with opener.open(url + "/healthz", timeout=2) as response:
            assert response.status == 200
            assert b'"ok":true' in response.read().replace(b' ', b'')
        print("ISOLATED_HTTPS_PROXY_READY=YES")
        break
    except (OSError, urllib.error.URLError, AssertionError):
        time.sleep(0.5)
else:
    raise SystemExit("ERROR: Isolated HTTPS proxy not ready")
PY
echo "=== OFFLINE FOOD AND LABS BROWSER TESTS + LIVE NAVIGATION ==="
set +e
env -i HOME=/root PATH=/usr/local/bin:/usr/bin:/bin \
  PYTHONPATH="$SOURCE" TRACKER_DATA_DIR="$DATA" \
  TRACKER_TEST_URL="$URL" TRACKER_TEST_HTTPS_URL="$HTTPS_URL" \
  TRACKER_TEST_ISOLATED=1 TRACKER_BROWSER_QA_DATA_DIR="$DATA" \
  PYTHONDONTWRITEBYTECODE=1 \
  "$PY" -B -m pytest -q -x --tb=short \
    tests/browser/test_food_search_ui.py \
    tests/browser/test_labs_overview.py \
    tests/browser/test_food_labs_live499.py \
    tests/browser/test_food_labs_mutations500.py \
    tests/browser/test_labs_native_https501.py \
    tests/browser/test_navigation.py >"$TEST_LOG" 2>&1
BROWSER_EXIT=$?
set -e
cat "$TEST_LOG"
echo "BROWSER_PYTEST_EXIT=$BROWSER_EXIT"
(( BROWSER_EXIT == 0 )) || exit "$BROWSER_EXIT"
