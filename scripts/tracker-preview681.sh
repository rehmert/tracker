#!/usr/bin/env bash
# Release 681: pinned DEV isolated preview, never installs.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
BASE=a8bd5a5a09a3e8274944b24e366a8b4840bcb9df
REF=release/681-compact-workout-navigation
PY="$APP/.venv/bin/python"
fail(){ echo "RELEASE_681_PREVIEW_ERROR=$*" >&2; exit 1; }
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] || fail "Root on tracker-dev required"
[[ -x "$PY" ]] || fail "Missing configured Python"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] || fail "Require clean main"
[[ "$(git rev-parse HEAD)" == "$BASE" ]] || fail "DEV baseline must be installed Release 680"
git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(git rev-parse "refs/remotes/origin/$REF")"
[[ "$TARGET" =~ ^[0-9a-f]{40}$ ]] || fail "Invalid target"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Target not descended from DEV baseline"
ROOT="$(mktemp -d /tmp/tracker-681-preview.XXXXXXXX)"
QA="$ROOT/source"
cleanup(){
 code=$?
 trap - EXIT
 if [[ -d "$QA" ]]; then git -C "$APP" worktree remove --force "$QA" >/dev/null 2>&1 || true; fi
 rm -rf -- "$ROOT"
 echo "RELEASE_681_PREVIEW_EXIT_STATUS=$code"
 exit "$code"
}
trap cleanup EXIT
git worktree add --detach "$QA" "$TARGET"
export GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP" GIT_CONFIG_KEY_1=safe.directory GIT_CONFIG_VALUE_1="$QA"
export PYTHONPATH="$QA" TRACKER_DATA_DIR="$ROOT/test-data"
mkdir -p "$TRACKER_DATA_DIR"
cd "$QA"
git diff --check "$BASE" "$TARGET"
EXPECTED="$(printf '%s\n' \
 app/static/css/tracker-workout-nav-density681.css \
 app/templates/base.html \
 tests/test_workout_nav_density681.py \
 scripts/tracker-release-scoped681.sh \
 scripts/tracker-preview681.sh | LC_ALL=C sort)"
ACTUAL="$(git diff --name-only "$BASE" "$TARGET" | LC_ALL=C sort)"
[[ "$ACTUAL" == "$EXPECTED" ]] || fail "Unexpected change set"
bash scripts/tracker-release-scoped681.sh "$PY"
echo "RELEASE_681_PREVIEW_QUALIFIED=$TARGET"
echo "RELEASE_681_PREVIEW=PASSED_ISOLATED_NO_INSTALL"
