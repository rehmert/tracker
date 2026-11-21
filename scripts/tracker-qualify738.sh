#!/usr/bin/env bash
# Release 738: isolated integrated MACD and mobile UX/CSS consolidation; never install.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=0ab7519d9d6b18cce03cc1db59fd9fbbaa1a151b
REF=release/738-integrated-macd-mobile-ux
fail() { echo "RELEASE_738_BLOCKED=$*" >&2; exit 1; }
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
  fail "Clean installed Release 737 required"
systemctl is-active --quiet tracker || fail "Installed DEV service inactive"
exec 9>/run/lock/tracker738-integrated-macd-mobile-ux.lock
flock -n 9 || fail "Another Release 738 QA active"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail "Fetched Release 738 branch SHA mismatch"
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Candidate must descend from Release 737"
git diff --check "$BASE" "$TARGET"
while IFS= read -r path; do
  case "$path" in
    app/routers/regimen635.py|\
    app/templates/regimen635.html|\
    app/templates/food.html|\
    app/templates/workouts654.html|\
    app/templates/workout_quick659.html|\
    app/static/css/tracker-food-core738.css|\
    app/static/css/tracker-action-flow738.css|\
    docs/release-738-integrated-macd-mobile-ux.md|\
    docs/tracker-macd-capability-matrix738.md|\
    scripts/tracker-install738.sh|\
    scripts/tracker-qualify738.sh|\
    scripts/tracker-release-scoped738.sh|\
    tests/test_release738_integrated_macd_mobile.py|\
    tests/test_action_navigation675.py|\
    tests/test_integrated_flow696.py|\
    tests/test_food_mobile424.py|\
    tests/test_food_accordion382.py ) ;;
    *) fail "Unexpected Release 738 source path: $path" ;;
  esac
done < <(git diff --name-only "$BASE" "$TARGET")
RUN="$(mktemp -d /tmp/tracker738-integrated-macd-mobile-ux.XXXXXXXX)"
QA="$RUN/source"
cleanup() {
  local code=$?
  trap - EXIT
  if [[ -d "$QA" ]] &&
     ! git -C "$APP" worktree remove --force "$QA"; then
    echo "RELEASE_738_BLOCKED=Source worktree cleanup failed" >&2
    code=1
  fi
  rm -rf -- "$RUN"
  if [[ "$(git -C "$APP" rev-parse HEAD)" != "$BASE" ||
        "$(git -C "$APP" branch --show-current)" != main ||
        -n "$(git -C "$APP" status --porcelain)" ]]; then
    echo "RELEASE_738_BLOCKED=Installed DEV source changed" >&2
    code=1
  fi
  echo "RELEASE_738_INSTALLED_DEV=UNMODIFIED"
  echo "RELEASE_738_EXIT_STATUS=$code"
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
bash -n scripts/tracker-qualify738.sh
bash -n scripts/tracker-release-scoped738.sh
bash -n scripts/tracker-install738.sh
bash -n scripts/tracker-release.sh
bash -n scripts/tracker-browser-qualify.sh
bash -n scripts/tracker-release-scoped738.sh
"$PY" -B scripts/tracker-impact-preflight604.py \
  --base "$BASE" --target "$TARGET" --root "$QA"
echo "RELEASE_738_IMPACT_PREFLIGHT=PASSED"
bash scripts/tracker-release-scoped738.sh "$PY"
echo "RELEASE_738_QUALIFICATION=PASSED_SCOPED_NO_DEPLOY"
