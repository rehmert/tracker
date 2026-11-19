#!/usr/bin/env bash
# Release 695: isolated Today and Quick Entry presentation preview.
# Never installs, promotes, or reads the installed Tracker SQLite database.
set -Eeuo pipefail
umask 077

APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=6a44ab33176cc6586066e0621774e539049ff338
REF=release/695-daily-flow

fail() { echo "RELEASE_695_PREVIEW_ERROR=$*" >&2; exit 1; }
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev &&
   -n "$(printenv INVOCATION_ID || true)" ]] ||
  fail "Must run as a root systemd worker on tracker-dev"
[[ -x "$PY" && -d "$APP/.git" ]] || fail "Configured DEV Python/repository unavailable"

cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] ||
  fail "Require clean installed DEV main"
[[ "$(git rev-parse HEAD)" == "$BASE" ]] ||
  fail "DEV must be installed at the Release 694 baseline"
systemctl is-active --quiet tracker || fail "DEV Tracker service inactive"

git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(git rev-parse "refs/remotes/origin/$REF")"
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Candidate does not descend from Release 694"
[[ "$(git rev-list --count "$BASE..$TARGET")" -ge 1 ]] ||
  fail "Candidate contains no changes"
git diff --check "$BASE" "$TARGET"

# Refuse unrelated changes: daily presentation, scoped tests, docs and gates only.
while IFS= read -r path; do
  case "$path" in
    app/templates/mobile_today509.html|app/templates/quick_entry.html|\
    app/static/css/tracker-today695.css|tests/test_daily_flow695.py|\
    tests/browser/test_daily_flow695.py|scripts/tracker-preview695.sh|\
    scripts/tracker-release-scoped695.sh|docs/release-695-daily-flow.md) ;;
    *) fail "Out-of-scope candidate path: $path" ;;
  esac
done < <(git diff --name-only "$BASE" "$TARGET")

RUN="$(mktemp -d /tmp/tracker-preview695.XXXXXXXX)"
QA="$RUN/source"
SERVER_PID=""
SERVER_LOG="$RUN/uvicorn.log"
cleanup() {
  code=$?
  trap - EXIT
  if [[ -n "$SERVER_PID" ]]; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
  if ((code != 0)) && [[ -f "$SERVER_LOG" ]]; then
    echo "=== ISOLATED SERVER LOG ==="
    tail -n 30 "$SERVER_LOG" || true
  fi
  if [[ -d "$QA" ]]; then
    git -C "$APP" worktree remove --force "$QA" >/dev/null 2>&1 || true
  fi
  rm -rf -- "$RUN"
  echo "RELEASE_695_PREVIEW_EXIT_STATUS=$code"
  exit "$code"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

git worktree add --detach "$QA" "$TARGET"
export GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP" \
  GIT_CONFIG_KEY_1=safe.directory GIT_CONFIG_VALUE_1="$QA"
export PYTHONPATH="$QA" TRACKER_DATA_DIR="$RUN/test-data"
mkdir -m 700 "$TRACKER_DATA_DIR"
cd "$QA"

bash scripts/tracker-release-scoped695.sh "$PY"

# Run only focused browser daily-workflow tests against an isolated loopback
# candidate. Never point Playwright at installed DEV or production.
VENDOR_SRC="$APP/app/static/vendor/htmx.min.js"
VENDOR_DST="$QA/app/static/vendor/htmx.min.js"
[[ -f "$VENDOR_SRC" && ! -L "$VENDOR_SRC" &&
   ! -e "$VENDOR_DST" && ! -L "$VENDOR_DST" ]] ||
  fail "Isolated trusted HTMX vendor prerequisites not met"
mkdir -p "$(dirname "$VENDOR_DST")"
install -m 0644 "$VENDOR_SRC" "$VENDOR_DST"
cmp -s "$VENDOR_SRC" "$VENDOR_DST" || fail "HTMX vendor copy mismatch"

PORT="$("$PY" - <<'PY'
import socket
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
)"
URL="http://127.0.0.1:$PORT"
env -i HOME=/root PATH=/usr/local/bin:/usr/bin:/bin \
  PYTHONPATH="$QA" TRACKER_DATA_DIR="$TRACKER_DATA_DIR" \
  TRACKER_INSTANCE=DEV PYTHONDONTWRITEBYTECODE=1 \
  "$PY" -B -m uvicorn app.main:app --host 127.0.0.1 \
  --port "$PORT" --app-dir "$QA" > "$SERVER_LOG" 2>&1 &
SERVER_PID=$!

"$PY" - "$URL" "$SERVER_PID" <<'PY'
import os
import sys
import time
import urllib.request
url, pid = sys.argv[1], int(sys.argv[2])
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
for _ in range(60):
    try:
        os.kill(pid, 0)
        with opener.open(url + "/healthz", timeout=2) as reply:
            assert reply.status == 200
            assert b'"ok":true' in reply.read().replace(b' ', b'')
        with opener.open(url + "/mobile", timeout=5) as reply:
            assert reply.status == 200
            assert b'aria-label="Record today"' in reply.read()
        with opener.open(url + "/quick-entry", timeout=5) as reply:
            assert reply.status == 200
            assert b'data-quick-search' in reply.read()
        print("RELEASE_695_ISOLATED_SERVER_READY=YES")
        break
    except (OSError, AssertionError):
        time.sleep(0.5)
else:
    raise SystemExit("Isolated candidate did not become ready")
PY

TRACKER_TEST_URL="$URL" TRACKER_TEST_ISOLATED=1 \
  "$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/browser/test_daily_flow695.py
echo "RELEASE_695_DAILY_BROWSER=PASSED"
echo "RELEASE_695_TEST_SCOPE=DAILY_WORKFLOW_FOCUSED_NO_FULL_SUITE"
echo "RELEASE_695_PREVIEW_QUALIFIED=$TARGET"
echo "RELEASE_695_PREVIEW=PASSED_ISOLATED_NO_INSTALL"
