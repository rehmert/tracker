#!/usr/bin/env bash
# Release 745: concurrent Work-task coordination contract and guarded scoped regressions; never install.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=0e9925532127eab2c939fb4ed5c045c6bf0dbe11
REF=release/745-macd-mobile-controller
fail() { echo "RELEASE_745_BLOCKED=$*" >&2; exit 1; }
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
  fail "Clean installed Release 744 required"
systemctl is-active --quiet tracker || fail "Installed DEV service inactive"
exec 9>/run/lock/tracker745-release-coordination.lock
flock -n 9 || fail "Another Release 745 QA active"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail "Fetched Release 745 branch SHA mismatch"
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Candidate must descend from Release 744"
git diff --check "$BASE" "$TARGET"
while IFS= read -r path; do
  case "$path" in
    app/routers/food.py|\
    app/templates/food.html|\
    app/templates/workout_quick659.html|\
    app/static/css/tracker-workout-gym-bundle745.css|\
    app/static/css/tracker-food-ux673.css|\
    scripts/tracker-release-agent745.py|\
    scripts/tracker-qualify745.sh|\
    scripts/tracker-install745.sh|\
    scripts/tracker-release-scoped745.sh|\
    tests/test_release745_controller.py|\
    tests/test_release745_macd_css.py|\
    tests/test_release738_integrated_macd_mobile.py|\
    tests/test_food_water425.py|\
    tests/test_integrated_mobile_ux673.py|\
    tests/test_release724_nav_dedup.py|\
    tests/test_workouts662.py|\
    tests/test_integrated_flow696.py|\
    tests/test_action_navigation675.py|\
    docs/release-745-consolidated.md|\
    docs/tracker-macd-capability-matrix745.md) ;;
    *) fail "Unexpected Release 745 source path: $path" ;;
  esac
done < <(git diff --name-only "$BASE" "$TARGET")
RUN="$(mktemp -d /tmp/tracker745-release-coordination.XXXXXXXX)"
QA="$RUN/source"
cleanup() {
  local code=$?
  trap - EXIT
  if [[ -d "$QA" ]] &&
     ! git -C "$APP" worktree remove --force "$QA"; then
    echo "RELEASE_745_BLOCKED=Source worktree cleanup failed" >&2
    code=1
  fi
  rm -rf -- "$RUN"
  if [[ "$(git -C "$APP" rev-parse HEAD)" != "$BASE" ||
        "$(git -C "$APP" branch --show-current)" != main ||
        -n "$(git -C "$APP" status --porcelain)" ]]; then
    echo "RELEASE_745_BLOCKED=Installed DEV source changed" >&2
    code=1
  fi
  echo "RELEASE_745_INSTALLED_DEV=UNMODIFIED"
  echo "RELEASE_745_EXIT_STATUS=$code"
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
bash -n scripts/tracker-qualify745.sh
bash -n scripts/tracker-release-scoped745.sh
bash -n scripts/tracker-install745.sh
bash -n scripts/tracker-release.sh
bash -n scripts/tracker-browser-qualify.sh
bash -n scripts/tracker-release-scoped745.sh
"$PY" -B scripts/tracker-impact-preflight604.py \
  --base "$BASE" --target "$TARGET" --root "$QA"
echo "RELEASE_745_IMPACT_PREFLIGHT=PASSED"
bash scripts/tracker-release-scoped745.sh "$PY"
echo "RELEASE_745_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY"
