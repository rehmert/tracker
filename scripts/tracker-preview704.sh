#!/usr/bin/env bash
# Release 704: single consolidated UX milestone — no install or PROD changes.
# Root DEV systemd-run, pinned 703, detached worktrees, empty SQLite,
# focused historical tests + 150-viewports + 698 136-image visual gate.
set -Eeuo pipefail
umask 077

APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=17e7a68daf8cb9a0c6219b162a54b9e7a1b9f8e2
REF=release/704-consolidated-ux-quality

fail() { echo "RELEASE_704_PREVIEW_ERROR=$*" >&2; exit 1; }
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev &&
   -n "$(printenv INVOCATION_ID || true)" ]] ||
  fail "Run only as root systemd worker on tracker-dev"
[[ -x "$PY" && -d "$APP/.git" ]] || fail "DEV Python or Git unavailable"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] ||
  fail "Require clean installed DEV main"
[[ "$(git rev-parse HEAD)" == "$BASE" ]] ||
  fail "DEV must run the exact verified Release 703 baseline"
systemctl is-active --quiet tracker || fail "Installed DEV service inactive"

git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(git rev-parse "refs/remotes/origin/$REF")"
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Candidate must descend from Release 703"
[[ "$(git rev-list --count "$BASE..$TARGET")" -ge 1 ]] ||
  fail "No candidate changes"
git diff --check "$BASE" "$TARGET"

# Strict 14-path limit. No application security, routing, DB, or dependency files.
while IFS= read -r path; do
  case "$path" in
    app/templates/dose_edit.html|\
    app/templates/page_edit.html|\
    app/templates/workout_backfill658.html|\
    app/templates/preparation_edit.html|\
    app/templates/lab_form.html|\
    app/static/css/tracker-edit-actions704.css|\
    app/static/js/tracker-edit-feedback704.js|\
    scripts/tracker-ux-audit704.py|\
    scripts/tracker-latency704.py|\
    tests/test_consolidated_ux704.py|\
    tests/browser/test_consolidated_ux704.py|\
    scripts/tracker-preview704.sh|\
    scripts/tracker-release-scoped704.sh|\
    docs/release-704-consolidated-ux-quality.md) ;;
    *) fail "Out-of-scope Release 704 candidate path: $path" ;;
  esac
done < <(git diff --name-only "$BASE" "$TARGET")

RUN="$(mktemp -d /tmp/tracker-preview704.XXXXXXXX)"
BASE_QA="$RUN/baseline"
CANDIDATE_QA="$RUN/candidate"
BASE_DATA="$RUN/base-data"
CANDIDATE_DATA="$RUN/test-data"
ARTIFACTS="$RUN/visual-diffs"
BASE_LOG="$RUN/baseline-uvicorn.log"
CANDIDATE_LOG="$RUN/candidate-uvicorn.log"
BASE_PID=""
CANDIDATE_PID=""
cleanup() {
  status=$?
  trap - EXIT
  for pid in "$BASE_PID" "$CANDIDATE_PID"; do
    if [[ -n "$pid" ]]; then
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
    fi
  done
  if (( status != 0 )); then
    echo "=== ISOLATED BASELINE LOG (last 25 lines) ==="
    [[ ! -f "$BASE_LOG" ]] || tail -n 25 "$BASE_LOG" || true
    echo "=== ISOLATED CANDIDATE LOG (last 25 lines) ==="
    [[ ! -f "$CANDIDATE_LOG" ]] || tail -n 25 "$CANDIDATE_LOG" || true
    if [[ -d "$ARTIFACTS" ]]; then
      PRIVATE="$(mktemp -d /tmp/tracker-visual704-review.XXXXXXXX)"
      chmod 700 "$PRIVATE"
      cp -a "$ARTIFACTS"/. "$PRIVATE"/
      echo "RELEASE_704_PRIVATE_VISUAL_DIFF_REVIEW=$PRIVATE"
    fi
  fi
  git -C "$APP" worktree remove --force "$CANDIDATE_QA" >/dev/null 2>&1 || true
  git -C "$APP" worktree remove --force "$BASE_QA" >/dev/null 2>&1 || true
  rm -rf -- "$RUN"
  echo "RELEASE_704_PREVIEW_EXIT_STATUS=$status"
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

bash scripts/tracker-release-scoped704.sh "$PY"

# Browser fixtures render actual Jinja templates against entirely synthetic
# records; submit is preventDefault, blocked HTTP has no write escape.
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/browser/test_consolidated_ux704.py \
  tests/browser/test_saved_food_mobile_actions702.py \
  tests/browser/test_mobile_edit_actions703.py \
  tests/test_mobile_dock_pointer603.py \
  tests/test_integrated_mobile_browser673.py
echo "RELEASE_704_CONSOLIDATED_BROWSER=PASSED"

# Baseline/candidate real app screenshots use independent private databases.
# HTMX vendor is not tracked by Git: copy trusted installed JS bytes, no download.
VENDOR_SRC="$APP/app/static/vendor/htmx.min.js"
[[ -f "$VENDOR_SRC" && ! -L "$VENDOR_SRC" ]] ||
  fail "Trusted installed HTMX vendor not available"
for checkout in "$BASE_QA" "$CANDIDATE_QA"; do
  DEST="$checkout/app/static/vendor/htmx.min.js"
  [[ ! -e "$DEST" && ! -L "$DEST" ]] ||
    fail "Unexpected candidate HTMX asset exists"
  mkdir -p "$(dirname "$DEST")"
  install -m 0644 "$VENDOR_SRC" "$DEST"
  cmp -s "$VENDOR_SRC" "$DEST" || fail "Vendor byte mismatch"
done

read -r BASE_PORT CANDIDATE_PORT < <("$PY" - <<'PY'
import socket
with socket.socket() as a, socket.socket() as b:
    a.bind(("127.0.0.1",0))
    b.bind(("127.0.0.1",0))
    print(a.getsockname()[1], b.getsockname()[1])
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
import os,sys,time
from urllib.request import build_opener, ProxyHandler
urls=sys.argv[1:3]
pids=[int(n) for n in sys.argv[3:5]]
opener=build_opener(ProxyHandler({}))
for url,pid in zip(urls,pids):
    for _ in range(80):
        try:
            os.kill(pid,0)
            with opener.open(url+"/healthz",timeout=2) as response:
                assert response.status==200
                assert b'"ok":true' in response.read().replace(b" ",b"")
            with opener.open(url+"/labs",timeout=5) as response:
                assert response.status==200
                assert b'<html' in response.read().lower()
            break
        except (OSError,AssertionError):
            time.sleep(.5)
    else:
        raise SystemExit("Candidate or baseline local server did not become ready")
print("RELEASE_704_BOTH_ISOLATED_SERVERS_READY=YES")
PY

# The existing cross-page visual gate should remain zero-regression because
# this release changes deeper edit pages, not its ten top-level screenshots.
TRACKER_TEST_ISOLATED=1 "$PY" scripts/tracker_visual_regression698.py \
  --baseline-url "$BASE_URL" \
  --candidate-url "$CANDIDATE_URL" \
  --artifact-dir "$ARTIFACTS"
echo "RELEASE_704_TOP_LEVEL_VISUAL=PASSED"

# Read-only latency baseline: no query tuning without measured evidence.
"$PY" scripts/tracker-latency704.py --url "$CANDIDATE_URL"
echo "RELEASE_704_TEST_SCOPE=CONSOLIDATED_MILESTONE_SCOPED_AND_VISUAL"
echo "RELEASE_704_PREVIEW_QUALIFIED=$TARGET"
echo "RELEASE_704_PREVIEW=PASSED_ISOLATED_NO_INSTALL"
