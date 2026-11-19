#!/usr/bin/env bash
# Release 700: pinned baseline vs candidate, synthetic/disposable page data only.
# Requires systemd-run root worker on tracker-dev, never installs or promotes.
set -Eeuo pipefail
umask 077

APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=a49cee23a1c3b87312a603a169be070fbe93faee
REF=release/700-shared-toolbar-css

fail() { echo "RELEASE_700_PREVIEW_ERROR=$*" >&2; exit 1; }
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev &&
   -n "$(printenv INVOCATION_ID || true)" ]] ||
  fail "Run only as root systemd worker on tracker-dev"
[[ -x "$PY" && -d "$APP/.git" ]] || fail "Missing configured DEV Python/repository"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] ||
  fail "DEV checkout must be clean main"
[[ "$(git rev-parse HEAD)" == "$BASE" ]] ||
  fail "DEV installed baseline must be verified Release 699"
systemctl is-active --quiet tracker || fail "Installed DEV Tracker service inactive"

git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(git rev-parse "refs/remotes/origin/$REF")"
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Candidate must descend from pinned Release 699"
[[ "$(git rev-list --count "$BASE..$TARGET")" -ge 1 ]] ||
  fail "No candidate changes"
git diff --check "$BASE" "$TARGET"

# Permit one shared CSS file, its cache tag, focused tests and docs.
while IFS= read -r file; do
  case "$file" in
    app/templates/base.html|\
    app/static/css/tracker-shortcuts-toolbar687.css|\
    tests/test_shortcuts_toolbar687.py|\
    tests/test_dashboard_polish688.py|\
    tests/test_css_consolidation700.py|\
    tests/browser/test_css_parity700.py|\
    scripts/tracker-release-scoped700.sh|\
    scripts/tracker-preview700.sh|\
    docs/release-700-shared-toolbar-css.md) ;;
    *) fail "Out-of-scope Release 700 path: $file" ;;
  esac
done < <(git diff --name-only "$BASE" "$TARGET")

RUN="$(mktemp -d /tmp/tracker-preview700.XXXXXXXX)"
BASE_QA="$RUN/baseline"
CANDIDATE_QA="$RUN/candidate"
BASE_DATA="$RUN/data-baseline"
CANDIDATE_DATA="$RUN/data-candidate"
ARTIFACTS="$RUN/visual-failures"
BASE_LOG="$RUN/base-server.log"
CANDIDATE_LOG="$RUN/candidate-server.log"
BASE_PID=""
CANDIDATE_PID=""
cleanup() {
  status=$?
  trap - EXIT
  for pid in "$CANDIDATE_PID" "$BASE_PID"; do
    if [[ -n "$pid" ]]; then
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
    fi
  done
  if ((status != 0)); then
    echo "=== RELEASE 699 BASELINE SERVER LOG (last 25 lines) ==="
    [[ ! -f "$BASE_LOG" ]] || tail -n 25 "$BASE_LOG" || true
    echo "=== RELEASE 699 CANDIDATE SERVER LOG (last 25 lines) ==="
    [[ ! -f "$CANDIDATE_LOG" ]] || tail -n 25 "$CANDIDATE_LOG" || true
    if [[ -d "$ARTIFACTS" ]]; then
      PRIVATE="$(mktemp -d /tmp/tracker-visual700-review.XXXXXXXX)"
      chmod 700 "$PRIVATE"
      cp -a "$ARTIFACTS"/. "$PRIVATE"/
      echo "RELEASE_700_PRIVATE_DIFF_REVIEW=$PRIVATE"
    fi
  fi
  git -C "$APP" worktree remove --force "$CANDIDATE_QA" >/dev/null 2>&1 || true
  git -C "$APP" worktree remove --force "$BASE_QA" >/dev/null 2>&1 || true
  rm -rf -- "$RUN"
  echo "RELEASE_700_PREVIEW_EXIT_STATUS=$status"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

git worktree add --detach "$BASE_QA" "$BASE"
git worktree add --detach "$CANDIDATE_QA" "$TARGET"
export GIT_CONFIG_COUNT=3 \
  GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP" \
  GIT_CONFIG_KEY_1=safe.directory GIT_CONFIG_VALUE_1="$BASE_QA" \
  GIT_CONFIG_KEY_2=safe.directory GIT_CONFIG_VALUE_2="$CANDIDATE_QA"

mkdir -m 700 "$BASE_DATA" "$CANDIDATE_DATA"
cd "$CANDIDATE_QA"
export PYTHONPATH="$CANDIDATE_QA" TRACKER_DATA_DIR="$CANDIDATE_DATA"

bash scripts/tracker-release-scoped700.sh "$PY"

# Exact computed-style and screenshot parity for shared toolbar, shortcuts
# and workout presentation: 5 widths × 3 densities × 2 themes × 2 modes.
TRACKER_CSS_PARITY700=1 \
TRACKER_700_BASE_SOURCE="$BASE_QA" \
TRACKER_700_CANDIDATE_SOURCE="$CANDIDATE_QA" \
  "$PY" -m pytest -q -s --tb=short --maxfail=1 \
  tests/browser/test_css_parity700.py
echo "RELEASE_700_CSS_PARITY_BROWSER=PASSED"

# htmx vendor is untracked at this installation; copy verified local bytes
# to each isolated source checkout, with no network or dependency downloads.
VENDOR_SRC="$APP/app/static/vendor/htmx.min.js"
[[ -f "$VENDOR_SRC" && ! -L "$VENDOR_SRC" ]] || fail "Trusted local HTMX vendor unavailable"
for checkout in "$BASE_QA" "$CANDIDATE_QA"; do
  destination="$checkout/app/static/vendor/htmx.min.js"
  [[ ! -e "$destination" && ! -L "$destination" ]] ||
    fail "Unexpected preexisting HTMX vendor in worktree"
  mkdir -p "$(dirname "$destination")"
  install -m 0644 "$VENDOR_SRC" "$destination"
  cmp -s "$VENDOR_SRC" "$destination" || fail "HTMX copy mismatch"
done

read -r BASE_PORT CANDIDATE_PORT < <("$PY" - <<'PY'
import socket
with socket.socket() as first, socket.socket() as second:
    first.bind(("127.0.0.1", 0))
    second.bind(("127.0.0.1", 0))
    print(first.getsockname()[1], second.getsockname()[1])
PY
)
BASE_URL="http://127.0.0.1:$BASE_PORT"
CANDIDATE_URL="http://127.0.0.1:$CANDIDATE_PORT"

env -i HOME=/root PATH=/usr/local/bin:/usr/bin:/bin \
  PYTHONPATH="$BASE_QA" TRACKER_DATA_DIR="$BASE_DATA" \
  TRACKER_INSTANCE=DEV PYTHONDONTWRITEBYTECODE=1 \
  "$PY" -B -m uvicorn app.main:app --host 127.0.0.1 \
  --port "$BASE_PORT" --app-dir "$BASE_QA" > "$BASE_LOG" 2>&1 &
BASE_PID=$!
env -i HOME=/root PATH=/usr/local/bin:/usr/bin:/bin \
  PYTHONPATH="$CANDIDATE_QA" TRACKER_DATA_DIR="$CANDIDATE_DATA" \
  TRACKER_INSTANCE=DEV PYTHONDONTWRITEBYTECODE=1 \
  "$PY" -B -m uvicorn app.main:app --host 127.0.0.1 \
  --port "$CANDIDATE_PORT" --app-dir "$CANDIDATE_QA" > "$CANDIDATE_LOG" 2>&1 &
CANDIDATE_PID=$!

"$PY" - "$BASE_URL" "$CANDIDATE_URL" "$BASE_PID" "$CANDIDATE_PID" <<'PY'
import os
import sys
import time
from urllib.request import build_opener, ProxyHandler
urls, pids = sys.argv[1:3], [int(x) for x in sys.argv[3:5]]
opener = build_opener(ProxyHandler({}))
for url, pid in zip(urls, pids):
    for attempt in range(70):
        try:
            os.kill(pid, 0)
            with opener.open(url + "/healthz", timeout=2) as response:
                assert response.status == 200
                assert b'"ok":true' in response.read().replace(b" ", b"")
            with opener.open(url + "/coas", timeout=5) as response:
                assert response.status == 200
                assert b'<html' in response.read().lower()
            break
        except (OSError, AssertionError):
            time.sleep(0.5)
    else:
        raise SystemExit("Isolated server did not become ready")
print("RELEASE_700_BOTH_ISOLATED_SERVERS_READY=YES")
PY

# Both loopback origins use separate disposable DBs. No installed/live data.
TRACKER_TEST_ISOLATED=1 "$PY" scripts/tracker_visual_regression698.py \
  --baseline-url "$BASE_URL" \
  --candidate-url "$CANDIDATE_URL" \
  --artifact-dir "$ARTIFACTS"
echo "TRACKER_699_TEST_BROWSER=PASSED"
echo "RELEASE_700_VISUAL_BROWSER=PASSED"
echo "RELEASE_700_TEST_SCOPE=SHARED_CSS_PARITY_AND_REAL_PAGE_VISUAL_NO_FULL_SUITE"
echo "RELEASE_700_PREVIEW_QUALIFIED=$TARGET"
echo "RELEASE_700_PREVIEW=PASSED_ISOLATED_NO_INSTALL"