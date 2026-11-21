#!/usr/bin/env bash
# Release 719: only isolated workout-management DEV qualification, never deploy/install anything.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=18a1bf7a6171ef1eeef80e4588851cd500031cb4
REF=release/719-workout-delete-dashboard-pagination
fail() { echo "RELEASE_719_BLOCKED=$*" >&2; exit 1; }
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
  fail "Clean installed Release 718 required"
systemctl is-active --quiet tracker || fail "Installed DEV service inactive"
exec 9>/run/lock/tracker719-workout-management.lock
flock -n 9 || fail "Another Release 719 QA active"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail "Fetched Release 719 branch SHA mismatch"
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Candidate must descend from Release 718"
git diff --check "$BASE" "$TARGET"
while IFS= read -r path; do
  case "$path" in
    app/routers/dashboard.py|\
    app/routers/workouts668.py|\
    app/workout_dashboard661.py|\
    app/templates/_workout_dashboard661.html|\
    app/templates/_workout_delete719.html|\
    app/templates/dashboard.html|\
    app/templates/workout_history654.html|\
    app/templates/workout_quick659.html|\
    app/templates/workout_review663.html|\
    app/templates/workouts654.html|\
    app/static/css/tracker-workout-dashboard661.css|\
    app/static/css/tracker-workout-session719.css|\
    docs/release-719-workout-management.md|\
    scripts/tracker-browser-qualify.sh|\
    scripts/tracker-install719.sh|\
    scripts/tracker-qualify719.sh|\
    scripts/tracker-release-scoped719.sh|\
    scripts/tracker-release.sh|\
    tests/browser/test_workout_dashboard661.py|\
    tests/browser/test_workout_manage719.py|\
    tests/test_browser_qualification511.py|\
    tests/test_release719_workout_history.py|\
    tests/test_workout_dashboard661.py|\
    tests/test_workout_activity_cards678.py|\
    tests/test_overview_css_order682.py|\
    tests/test_overview_density690.py) ;;
    *) fail "Unexpected Release 719 source path: $path" ;;
  esac
done < <(git diff --name-only "$BASE" "$TARGET")
RUN="$(mktemp -d /tmp/tracker719-workout-management.XXXXXXXX)"
QA="$RUN/source"
cleanup() {
  local code=$?
  trap - EXIT
  if [[ -d "$QA" ]] &&
     ! git -C "$APP" worktree remove --force "$QA"; then
    echo "RELEASE_719_BLOCKED=Source worktree cleanup failed" >&2
    code=1
  fi
  rm -rf -- "$RUN"
  if [[ "$(git -C "$APP" rev-parse HEAD)" != "$BASE" ||
        "$(git -C "$APP" branch --show-current)" != main ||
        -n "$(git -C "$APP" status --porcelain)" ]]; then
    echo "RELEASE_719_BLOCKED=Installed DEV source changed" >&2
    code=1
  fi
  echo "RELEASE_719_INSTALLED_DEV=UNMODIFIED"
  echo "RELEASE_719_EXIT_STATUS=$code"
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
bash -n scripts/tracker-qualify719.sh
bash -n scripts/tracker-install719.sh
bash -n scripts/tracker-release.sh
bash -n scripts/tracker-browser-qualify.sh
bash -n scripts/tracker-release-scoped719.sh
"$PY" -B scripts/tracker-impact-preflight604.py \
  --base "$BASE" --target "$TARGET" --root "$QA"
echo "RELEASE_719_IMPACT_PREFLIGHT=PASSED"
bash scripts/tracker-release-scoped719.sh "$PY"
echo "RELEASE_719_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY"
