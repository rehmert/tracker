#!/usr/bin/env bash
# Release 739: isolated Workout/Food MACD and mobile CSS consolidation; never install.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=de867eee93004534fa822e7250deda75d0976558
REF=release/739-workout-food-macd-mobile
fail() { echo "RELEASE_739_BLOCKED=$*" >&2; exit 1; }
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] ||
  fail "Expected exact candidate SHA"
TARGET="$1"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev &&
   -n "${INVOCATION_ID:-}" ]] || fail "Root systemd worker on tracker-dev required"
[[ "$(readlink /proc/self/ns/net)" != "$(readlink /proc/1/ns/net)" ]] ||
  fail "PrivateNetwork=yes required"
[[ -x "$PY" && -d "$APP/.git" ]] || fail "Installed DEV source missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main &&
   "$(git rev-parse HEAD)" == "$BASE" &&
   -z "$(git status --porcelain)" ]] ||
  fail "Clean installed Release 738 required"
systemctl is-active --quiet tracker || fail "Installed DEV service inactive"
exec 9>/run/lock/tracker739-workout-food-macd-mobile.lock
flock -n 9 || fail "Another Release 739 QA active"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail "Fetched Release 739 branch SHA mismatch"
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Candidate must descend from Release 738"
git diff --check "$BASE" "$TARGET"
while IFS= read -r path; do
  case "$path" in
    app/routers/workouts655.py|\
    app/routers/food.py|\
    app/templates/workout_routines655.html|\
    app/templates/workout_routine_detail655.html|\
    app/templates/food_saved_edit669.html|\
    app/static/css/tracker-workout-routines739.css|\
    app/static/css/tracker-saved-food-actions702.css|\
    docs/release-739-workout-food-macd-mobile.md|\
    docs/tracker-macd-capability-matrix739.md|\
    scripts/tracker-qualify739.sh|\
    scripts/tracker-install739.sh|\
    scripts/tracker-release-scoped739.sh|\
    tests/test_release739_workout_food_macd_mobile.py|\
    tests/test_release714_routine_alignment.py|\
    tests/test_saved_food_mobile_actions702.py ) ;;
    *) fail "Unexpected Release 739 source path: $path" ;;
  esac
done < <(git diff --name-only "$BASE" "$TARGET")
RUN="$(mktemp -d /tmp/tracker739-workout-food-macd-mobile.XXXXXXXX)"
QA="$RUN/source"
cleanup() {
  local code=$?
  trap - EXIT
  if [[ -d "$QA" ]] &&
     ! git -C "$APP" worktree remove --force "$QA"; then
    echo "RELEASE_739_BLOCKED=Source worktree cleanup failed" >&2
    code=1
  fi
  rm -rf -- "$RUN"
  if [[ "$(git -C "$APP" rev-parse HEAD)" != "$BASE" ||
        "$(git -C "$APP" branch --show-current)" != main ||
        -n "$(git -C "$APP" status --porcelain)" ]]; then
    echo "RELEASE_739_BLOCKED=Installed DEV source changed" >&2
    code=1
  fi
  echo "RELEASE_739_INSTALLED_DEV=UNMODIFIED"
  echo "RELEASE_739_EXIT_STATUS=$code"
  exit "$code"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
git worktree add --detach "$QA" "$TARGET"
[[ "$(git -C "$QA" rev-parse HEAD)" == "$TARGET" ]] ||
  fail "QA worktree differs from exact target"
export GIT_CONFIG_COUNT=2
export GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
export GIT_CONFIG_KEY_1=safe.directory GIT_CONFIG_VALUE_1="$QA"
mkdir -m 700 "$RUN/data"
cd "$QA"
export TRACKER_DATA_DIR="$RUN/data" PYTHONPATH="$QA" PYTHONDONTWRITEBYTECODE=1
bash -n scripts/tracker-qualify739.sh
bash -n scripts/tracker-release-scoped739.sh
bash -n scripts/tracker-install739.sh
bash -n scripts/tracker-release.sh
bash -n scripts/tracker-browser-qualify.sh
bash -n scripts/tracker-release-scoped739.sh
"$PY" -B scripts/tracker-impact-preflight604.py \
  --base "$BASE" --target "$TARGET" --root "$QA"
echo "RELEASE_739_IMPACT_PREFLIGHT=PASSED"
bash scripts/tracker-release-scoped739.sh "$PY"
echo "RELEASE_739_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY"
