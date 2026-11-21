#!/usr/bin/env bash
# Release 716: only isolated workout-machine DEV qualification, never deploy/install anything.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=ab70236618df66b8a959c765abf38dbcd59b29d7
REF=release/716-active-workout-machine-add
fail() { echo "RELEASE_716_BLOCKED=$*" >&2; exit 1; }
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
  fail "Clean installed Release 715 required"
systemctl is-active --quiet tracker || fail "Installed DEV service inactive"
exec 9>/run/lock/tracker716-active-workout.lock
flock -n 9 || fail "Another Release 716 QA active"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail "Fetched Release 716 branch SHA mismatch"
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Candidate must descend from Release 715"
git diff --check "$BASE" "$TARGET"
while IFS= read -r path; do
  case "$path" in
    app/routers/workouts659.py|\\
    app/templates/workout_quick659.html|\\
    app/static/css/tracker-workouts716.css|\\
    docs/release-716-active-workout.md|\\
    scripts/tracker-browser-qualify.sh|\\
    scripts/tracker-install716.sh|\\
    scripts/tracker-qualify716.sh|\\
    scripts/tracker-release-scoped716.sh|\\
    scripts/tracker-release.sh|\\
    tests/browser/test_workout_active716.py|\\
    tests/test_browser_qualification511.py|\\
    tests/test_release716_active_workout.py) ;;
    *) fail "Unexpected Release 716 source path: $path" ;;
  esac
done < <(git diff --name-only "$BASE" "$TARGET")
RUN="$(mktemp -d /tmp/tracker716-active-workout.XXXXXXXX)"
QA="$RUN/source"
cleanup() {
  local code=$?
  trap - EXIT
  if [[ -d "$QA" ]] &&
     ! git -C "$APP" worktree remove --force "$QA"; then
    echo "RELEASE_716_BLOCKED=Source worktree cleanup failed" >&2
    code=1
  fi
  rm -rf -- "$RUN"
  if [[ "$(git -C "$APP" rev-parse HEAD)" != "$BASE" ||
        "$(git -C "$APP" branch --show-current)" != main ||
        -n "$(git -C "$APP" status --porcelain)" ]]; then
    echo "RELEASE_716_BLOCKED=Installed DEV source changed" >&2
    code=1
  fi
  echo "RELEASE_716_INSTALLED_DEV=UNMODIFIED"
  echo "RELEASE_716_EXIT_STATUS=$code"
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
bash -n scripts/tracker-qualify716.sh
bash -n scripts/tracker-install716.sh
bash -n scripts/tracker-release.sh
bash -n scripts/tracker-browser-qualify.sh
bash -n scripts/tracker-release-scoped716.sh
"$PY" -B scripts/tracker-impact-preflight604.py \
  --base "$BASE" --target "$TARGET" --root "$QA"
echo "RELEASE_716_IMPACT_PREFLIGHT=PASSED"
bash scripts/tracker-release-scoped716.sh "$PY"
echo "RELEASE_716_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY"
