#!/usr/bin/env bash
# Release 709: DEV-only strict Chromium positive food and COA acceptance.
# Must be fetched from immutable GitHub SHA and run detached via systemd.
set -Eeuo pipefail
umask 077

APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=4c084ade9063b3b01c2de0a4a055d2e23470b2a3
REF=release/709-csrf-food-coa-positives
fail() { echo "RELEASE_709_BLOCKED=$*" >&2; exit 1; }

[[ "$#" == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] ||
  fail "Exactly one pinned candidate SHA is required"
TARGET="$1"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev &&
   -n "${INVOCATION_ID:-}" ]] ||
  fail "Root systemd worker on tracker-dev required"
[[ "$(readlink /proc/self/ns/net)" != "$(readlink /proc/1/ns/net)" ]] ||
  fail "PrivateNetwork=yes required"
[[ -x "$PY" && -d "$APP/.git" ]] ||
  fail "DEV Python or source missing"

cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main &&
   "$(git rev-parse HEAD)" == "$BASE" &&
   -z "$(git status --porcelain)" ]] ||
  fail "Installed DEV must be clean Release 705"
systemctl is-active --quiet tracker || fail "Installed DEV service inactive"
exec 9>/run/lock/tracker709-positive-csrf.lock
flock -n 9 || fail "Another Release 709 qualification is running"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail "Candidate SHA/ref mismatch"
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Candidate not descendant of installed Release 705"
git diff --check "$BASE" "$TARGET"

# Cumulative Release 707+708+709 exact audited changed source paths.
while IFS= read -r path; do
  case "$path" in
    docs/release-707-csrf-positive.md|\
    docs/release-708-csrf-remaining-workout.md|\
    docs/release-709-csrf-food-coa-positive.md|\
    scripts/tracker-browser-qualify.sh|\
    scripts/tracker-csrf-positive707.sh|\
    scripts/tracker-csrf-positive708.sh|\
    scripts/tracker-csrf-positive709.sh|\
    tests/browser/test_csrf_regimen_catalog707.py|\
    tests/browser/test_csrf_workout_lifecycles707.py|\
    tests/browser/test_csrf_remaining_workout708.py|\
    tests/browser/test_csrf_food_coa709.py|\
    tests/test_browser_qualification511.py|\
    tests/test_release707_csrf_positive.py|\
    tests/test_release708_csrf_remaining.py|\
    tests/test_release709_csrf_food_coa.py) ;;
    *) fail "Unreviewed Release 709 path: $path" ;;
  esac
done < <(git diff --name-only "$BASE" "$TARGET")

RUN="$(mktemp -d /tmp/tracker709-csrf-preview.XXXXXXXX)"
QA="$RUN/candidate"
cleanup() {
  local status=$?
  trap - EXIT
  if [[ -d "$QA" ]] &&
     ! git -C "$APP" worktree remove --force "$QA"; then
    echo "RELEASE_709_BLOCKED=Detached candidate cleanup failure" >&2
    status=1
  fi
  rm -rf -- "$RUN"
  if [[ "$(git -C "$APP" rev-parse HEAD)" != "$BASE" ||
       "$(git -C "$APP" branch --show-current)" != main ||
       -n "$(git -C "$APP" status --porcelain)" ]]; then
    echo "RELEASE_709_BLOCKED=Installed DEV changed" >&2
    status=1
  fi
  echo "RELEASE_709_INSTALLED_DEV=UNMODIFIED"
  echo "RELEASE_709_EXIT_STATUS=$status"
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

git worktree add --detach "$QA" "$TARGET"
[[ "$(git -C "$QA" rev-parse HEAD)" == "$TARGET" ]] ||
  fail "Detached candidate HEAD differs"
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
bash -n scripts/tracker-csrf-positive709.sh
"$PY" -B -m pytest -q --tb=short --maxfail=1 \
  tests/test_release707_csrf_positive.py \
  tests/test_release708_csrf_remaining.py \
  tests/test_release709_csrf_food_coa.py \
  tests/test_release627_csrf_reconciliation.py \
  tests/test_browser_qualification511.py::test_511_every_browser_module_in_disposable_qualification
echo "RELEASE_709_SOURCE=PASSED"

bash scripts/tracker-browser-qualify.sh "$QA" "$PY" \
  --targeted-strict csrf-positive709

echo "RELEASE_709_TARGETED_FOOD_COA_10=PASSED_NOT_GLOBAL_CLEARANCE"
echo "RELEASE_709_NEW_REAL_SIGNED_ROUTE_COUNT=10"
echo "RELEASE_709_CUMULATIVE_NEW_SIGNED_ROUTE_COUNT=58"
echo "RELEASE_709_HISTORICAL_SOURCE_BACKLOG=92_UNRECONCILED"
echo "RELEASE_709_GLOBAL_CSRF=BLOCKED_OTHER_HISTORICAL_MANUAL_SESSION_REVIEW"
