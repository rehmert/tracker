#!/usr/bin/env bash
# Tracker Release 657: DEV-only isolated phone-sized browser functional QA.
# Never deploys, never modifies installed source/DB, never contacts PROD.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=b9487d4b1fab176255b398833c51c9a2da79f042
REF=qa/657-mobile-functional
fail() { echo "WORKOUT_MOBILE_657_QA=FAILED: $*" >&2; exit 1; }
[[ "$#" == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] ||
  fail "Pass exact reviewed mobile QA commit SHA"
EXPECTED="$1"
[[ "$(id -u)" == 0 && -x "$PY" && -f /etc/tracker.env ]] ||
  fail "Must run as root on configured Tracker DEV"
[[ "$(hostname -s)" == tracker-dev ]] || fail "Host must be tracker-dev"
g() { git -c safe.directory="$APP" -C "$APP" "$@"; }
[[ "$(g branch --show-current)" == main && -z "$(g status --porcelain)" ]] ||
  fail "Installed DEV checkout must be clean main"
[[ "$(g rev-parse HEAD)" == "$BASE" ]] ||
  fail "Installed DEV must be qualified Release 657"
systemctl is-active --quiet tracker || fail "Installed DEV service must be active"
"$PY" "$APP/scripts/tracker-instance-check653.py" --config /etc/tracker.env ||
  fail "DEV instance identity not verified"
g fetch origin main "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(g rev-parse "refs/remotes/origin/$REF")"
[[ "$TARGET" == "$EXPECTED" ]] || fail "QA branch differs from pinned SHA"
g merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "QA commit not descended from approved Release 657"
changed="$(g diff --name-only "$BASE" "$TARGET")"
[[ "$changed" == $'docs/workout-mobile-qa657.md\nscripts/tracker-workout-mobile-qa657.sh\ntests/browser/test_workouts_mobile657.py' ]] ||
  fail "QA branch contains non-allowlisted changes"
command -v openssl >/dev/null || fail "openssl required"
"$PY" - <<'PY'
import playwright.sync_api
import uvicorn
print("MOBILE_QA_DEPENDENCIES=AVAILABLE")
PY

ROOT="$(mktemp -d /tmp/tracker-mobileqa657.XXXXXXXX)"
SRC="$ROOT/source"
DATA="$ROOT/data"
mkdir -m 700 "$DATA"
SERVER_PID=""
PROXY_PID=""
cleanup() {
  code=$?
  trap - EXIT
  if [[ -n "$PROXY_PID" ]]; then
    kill "$PROXY_PID" 2>/dev/null || true
    wait "$PROXY_PID" 2>/dev/null || true
  fi
  if [[ -n "$SERVER_PID" ]]; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
  if [[ -d "$SRC" ]]; then
    g worktree remove --force "$SRC" >/dev/null 2>&1 || true
  fi
  # This root contains only disposable copied code, SQLite and TLS keys.
  rm -rf -- "$ROOT"
  echo "MOBILE_QA_657_DISPOSABLE_DATA_REMOVED=YES"
  exit "$code"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

g worktree add --detach "$SRC" "$TARGET"
[[ "$(git -C "$SRC" rev-parse HEAD)" == "$TARGET" ]] ||
  fail "Isolated source not pinned to requested SHA"

VENDOR_SRC="$APP/app/static/vendor/htmx.min.js"
VENDOR_DEST="$SRC/app/static/vendor/htmx.min.js"
[[ -f "$VENDOR_SRC" && ! -L "$VENDOR_SRC" ]] ||
  fail "Trusted installed local HTMX dependency unavailable"
if [[ ! -f "$VENDOR_DEST" ]]; then
  mkdir -p "$(dirname "$VENDOR_DEST")"
  install -m 0644 "$VENDOR_SRC" "$VENDOR_DEST"
fi
cmp -s "$VENDOR_SRC" "$VENDOR_DEST" || fail "Isolated HTMX differs from installed asset"

cd "$SRC"
"$PY" -m py_compile tests/browser/test_workouts_mobile657.py
bash -n scripts/tracker-workout-mobile-qa657.sh
git diff --check "$BASE" "$TARGET" ||
  fail "Source whitespace review failed"

port() {
  "$PY" - <<'PY'
import socket
with socket.socket() as s:
    s.bind(("127.0.0.1", 0))
    print(s.getsockname()[1])
PY
}
HTTP_PORT="$(port)"
HTTPS_PORT="$(port)"
[[ "$HTTP_PORT" != "$HTTPS_PORT" ]] || fail "Non-distinct test ports"
HTTP_URL="http://127.0.0.1:$HTTP_PORT"
HTTPS_URL="https://127.0.0.1:$HTTPS_PORT"

echo "MOBILE_QA_657_TARGET=$TARGET"
echo "MOBILE_QA_657_MODE=ISOLATED_HTTPS_STRICT_CSRF"
echo "MOBILE_QA_657_PROD=UNTOUCHED"
echo "MOBILE_QA_657_LIVE_DEV_DATA=UNTOUCHED"
env -i HOME=/root PATH=/usr/local/bin:/usr/bin:/bin \
  PYTHONPATH="$SRC" TRACKER_DATA_DIR="$DATA" TRACKER_INSTANCE=DEV \
  TRACKER_CSRF_ENFORCE=1 PYTHONDONTWRITEBYTECODE=1 \
  "$PY" -B -m uvicorn app.main:app --host 127.0.0.1 \
    --port "$HTTP_PORT" --app-dir "$SRC" >"$ROOT/uvicorn.log" 2>&1 &
SERVER_PID=$!

"$PY" - "$HTTP_URL" "$SERVER_PID" <<'PY'
import os, sys, time, urllib.error, urllib.request
url, pid = sys.argv[1], int(sys.argv[2])
client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
for attempt in range(80):
    try:
        os.kill(pid, 0)
        with client.open(url + "/healthz", timeout=2) as response:
            assert response.status == 200 and b'"ok":true' in response.read().replace(b" ", b"")
        print("MOBILE_QA_657_BACKEND_READY=YES")
        break
    except (OSError, AssertionError, urllib.error.URLError):
        time.sleep(.5)
else:
    raise SystemExit("Isolated backend did not become healthy")
PY

openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
  -subj '/CN=127.0.0.1' -addext 'subjectAltName=IP:127.0.0.1' \
  -keyout "$ROOT/key.pem" -out "$ROOT/cert.pem" >"$ROOT/openssl.log" 2>&1

env -i HOME=/root PATH=/usr/local/bin:/usr/bin:/bin \
  PYTHONDONTWRITEBYTECODE=1 \
  "$PY" -B scripts/tracker-tls-proxy501.py \
  --listen-port "$HTTPS_PORT" --backend-port "$HTTP_PORT" \
  --cert "$ROOT/cert.pem" --key "$ROOT/key.pem" >"$ROOT/tls.log" 2>&1 &
PROXY_PID=$!

"$PY" - "$HTTPS_URL" "$PROXY_PID" <<'PY'
import os, ssl, sys, time, urllib.error, urllib.request
url, pid = sys.argv[1], int(sys.argv[2])
client = urllib.request.build_opener(urllib.request.ProxyHandler({}),
    urllib.request.HTTPSHandler(context=ssl._create_unverified_context()))
for attempt in range(80):
    try:
        os.kill(pid, 0)
        with client.open(url + "/healthz", timeout=2) as response:
            assert response.status == 200
        print("MOBILE_QA_657_HTTPS_READY=YES")
        break
    except (OSError, AssertionError, urllib.error.URLError):
        time.sleep(.5)
else:
    raise SystemExit("Isolated HTTPS browser endpoint unavailable")
PY

echo "=== DISPOSABLE PHONE-VIEWPORT END-TO-END WORKOUT TESTS ==="
set +e
env -i HOME=/root PATH=/usr/local/bin:/usr/bin:/bin \
  PYTHONPATH="$SRC" TRACKER_DATA_DIR="$DATA" TRACKER_INSTANCE=DEV \
  TRACKER_TEST_HTTPS_URL="$HTTPS_URL" \
  TRACKER_BROWSER_QA_DATA_DIR="$DATA" TRACKER_TEST_ISOLATED=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  timeout 420 "$PY" -B -m pytest -q --tb=short --maxfail=1 -s \
  tests/browser/test_workouts_mobile657.py >"$ROOT/qa.log" 2>&1
RESULT=$?
set -e
cat "$ROOT/qa.log"
if (( RESULT != 0 )); then
  echo "MOBILE_QA_657_RESULT=FAILED exit=$RESULT" >&2
  echo "=== ISOLATED SERVER DIAGNOSTICS ===" >&2
  tail -n 25 "$ROOT/uvicorn.log" >&2
  exit "$RESULT"
fi
echo "MOBILE_QA_657_ANDROID_AND_IPHONE_EMULATION=PASSED"
echo "MOBILE_QA_657_NO_RELEASE_OR_LIVE_DB_MUTATION=VERIFIED"
echo "MOBILE_QA_657_RESULT=SUCCESS"
