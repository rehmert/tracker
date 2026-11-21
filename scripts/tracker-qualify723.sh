#!/usr/bin/env bash
# Release 723: only isolated workout-css-consolidation DEV qualification, never deploy/install anything.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=40088e446b66285aaa07caf40566e4de80864a98
REF=release/723-workout-css-consolidation
fail() { echo "RELEASE_723_BLOCKED=$*" >&2; exit 1; }
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
  fail "Clean installed Release 722 required"
systemctl is-active --quiet tracker || fail "Installed DEV service inactive"
exec 9>/run/lock/tracker723-workout-css-consolidation.lock
flock -n 9 || fail "Another Release 723 QA active"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail "Fetched Release 723 branch SHA mismatch"
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Candidate must descend from Release 722"
git diff --check "$BASE" "$TARGET"
while IFS= read -r path; do
  case "$path" in
    app/static/css/tracker-workout-gym667.css|\
    app/static/css/tracker-workout-ux673.css|\
    app/static/css/tracker-workouts659.css|\
    app/static/css/tracker-workouts662.css|\
    app/templates/workout_quick659.html|\
    docs/release-723-workout-css-consolidation.md|\
    scripts/tracker-install723.sh|\
    scripts/tracker-qualify723.sh|\
    scripts/tracker-release-scoped723.sh|\
    tests/browser/test_release723_css_parity.py|\
    tests/browser/test_workout_program667.py|\
    tests/browser/test_workout_targets666.py|\
    tests/browser/test_workouts_quick662.py|\
    tests/test_integrated_mobile_browser673.py|\
    tests/test_integrated_mobile_ux673.py|\
    tests/test_release723_css_consolidation.py|\
    tests/test_workouts662.py) ;;
    *) fail "Unexpected Release 723 source path: $path" ;;
  esac
done < <(git diff --name-only "$BASE" "$TARGET")
RUN="$(mktemp -d /tmp/tracker723-workout-css-consolidation.XXXXXXXX)"
QA="$RUN/source"
cleanup() {
  local code=$?
  trap - EXIT
  if [[ -d "$QA" ]] &&
     ! git -C "$APP" worktree remove --force "$QA"; then
    echo "RELEASE_723_BLOCKED=Source worktree cleanup failed" >&2
    code=1
  fi
  rm -rf -- "$RUN"
  if [[ "$(git -C "$APP" rev-parse HEAD)" != "$BASE" ||
        "$(git -C "$APP" branch --show-current)" != main ||
        -n "$(git -C "$APP" status --porcelain)" ]]; then
    echo "RELEASE_723_BLOCKED=Installed DEV source changed" >&2
    code=1
  fi
  echo "RELEASE_723_INSTALLED_DEV=UNMODIFIED"
  echo "RELEASE_723_EXIT_STATUS=$code"
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
bash -n scripts/tracker-qualify723.sh
bash -n scripts/tracker-install723.sh
bash -n scripts/tracker-release.sh
bash -n scripts/tracker-browser-qualify.sh
bash -n scripts/tracker-release-scoped723.sh
"$PY" -B scripts/tracker-impact-preflight604.py \
  --base "$BASE" --target "$TARGET" --root "$QA"
echo "RELEASE_723_IMPACT_PREFLIGHT=PASSED"
bash scripts/tracker-release-scoped723.sh "$PY"
echo "RELEASE_723_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY"
