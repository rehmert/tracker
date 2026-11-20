#!/usr/bin/env bash
# Release 708: detached, isolated REAL strict-CSRF Workout acceptance.
# Source loaded from immutable GitHub SHA. No LIVE DEV/PROD deployment.
set -Eeuo pipefail
umask 077

APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=4c084ade9063b3b01c2de0a4a055d2e23470b2a3
REF=release/708-csrf-remaining-workout-positives
fail() { echo "RELEASE_708_BLOCKED=$*" >&2; exit 1; }

[[ "$#" == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] ||
  fail "Exactly one pinned candidate SHA required"
TARGET="$1"

[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev &&
   -n "${INVOCATION_ID:-}" ]] || fail "Run as root in tracker-dev systemd"
[[ "$(readlink /proc/self/ns/net)" != "$(readlink /proc/1/ns/net)" ]] ||
  fail "PrivateNetwork=yes is mandatory"
[[ -x "$PY" && -d "$APP/.git" ]] ||
  fail "DEV installed source/interpreter unavailable"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP"

[[ "$(git branch --show-current)" == main &&
   "$(git rev-parse HEAD)" == "$BASE" &&
   -z "$(git status --porcelain)" ]] ||
  fail "Installed DEV must be clean Release 705"
systemctl is-active --quiet tracker || fail "Installed DEV service inactive"
exec 9>/run/lock/tracker708-positive-csrf.lock
flock -n 9 || fail "Another 708 qualification is running"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail "Exact candidate branch SHA not fetched"
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Candidate does not descend from installed DEV"
git diff --check "$BASE" "$TARGET"

# All files changed against installed DEV must be expected. No router,
# templates, migrations, installed requirements, or environment edits.
while IFS= read -r path; do
  case "$path" in
    docs/release-707-csrf-positive.md|\
    docs/release-708-csrf-remaining-workout.md|\
    scripts/tracker-browser-qualify.sh|\
    scripts/tracker-csrf-positive707.sh|\
    scripts/tracker-csrf-positive708.sh|\
    tests/browser/test_csrf_regimen_catalog707.py|\
    tests/browser/test_csrf_workout_lifecycles707.py|\
    tests/browser/test_csrf_remaining_workout708.py|\
    tests/test_browser_qualification511.py|\
    tests/test_release707_csrf_positive.py|\
    tests/test_release708_csrf_remaining.py) ;;
    *) fail "Unreviewed Release 708 path $path" ;;
  esac
done < <(git diff --name-only "$BASE" "$TARGET")

RUN="$(mktemp -d /tmp/tracker708-csrf-preview.XXXXXXXX)"
QA="$RUN/candidate"
cleanup() {
  local status=$?
  trap - EXIT
  if [[ -d "$QA" ]] &&
     ! git -C "$APP" worktree remove --force "$QA"; then
    echo "RELEASE_708_BLOCKED=Worktree cleanup failed" >&2
    status=1
  fi
  rm -rf -- "$RUN"
  if [[ "$(git -C "$APP" rev-parse HEAD)" != "$BASE" ||
       "$(git -C "$APP" branch --show-current)" != main ||
       -n "$(git -C "$APP" status --porcelain)" ]]; then
    echo "RELEASE_708_BLOCKED=Installed DEV source changed" >&2
    status=1
  fi
  echo "RELEASE_708_INSTALLED_DEV=UNMODIFIED"
  echo "RELEASE_708_EXIT_STATUS=$status"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

git worktree add --detach "$QA" "$TARGET"
[[ "$(git -C "$QA" rev-parse HEAD)" == "$TARGET" ]] ||
  fail "Detached commit mismatch"
export GIT_CONFIG_COUNT=2
export GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP"
export GIT_CONFIG_KEY_1=safe.directory
export GIT_CONFIG_VALUE_1="$QA"
mkdir -m 700 "$RUN/data"
cd "$QA"
export PYTHONPATH="$QA" TRACKER_DATA_DIR="$RUN/data"
export PYTHONDONTWRITEBYTECODE=1

bash -n scripts/tracker-browser-qualify.sh
bash -n scripts/tracker-csrf-positive708.sh
"$PY" -B -m pytest -q --tb=short --maxfail=1 \
  tests/test_release707_csrf_positive.py \
  tests/test_release708_csrf_remaining.py \
  tests/test_release627_csrf_reconciliation.py \
  tests/test_browser_qualification511.py::test_511_every_browser_module_in_disposable_qualification
echo "RELEASE_708_SOURCE=PASSED"

# Only NEW 19-route module; previous 29 already qualified on Release 707
# with real Chromium. The full strict suite includes both when required.
bash scripts/tracker-browser-qualify.sh "$QA" "$PY" \
  --targeted-strict csrf-positive708

echo "RELEASE_708_TARGETED_WORKOUT_19=PASSED_NOT_GLOBAL_CLEARANCE"
echo "RELEASE_708_NEW_REAL_SIGNED_ROUTE_COUNT=19"
echo "RELEASE_708_HISTORICAL_SOURCE_BACKLOG=92_UNRECONCILED"
echo "RELEASE_708_GLOBAL_CSRF=BLOCKED_UNTIL_ALL_ROUTES_AND_MANUAL_REVIEWS"
