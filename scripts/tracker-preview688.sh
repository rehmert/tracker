#!/usr/bin/env bash
# Release 688: isolated preview only, no DEV installation, no PROD access.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
BASE=6c47f765e76d4e4609f1d36c06226f439b28334d
REF=release/688-dashboard-polish
PY="$APP/.venv/bin/python"
fail(){ echo "RELEASE_688_PREVIEW_ERROR=$*" >&2; exit 1; }
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] ||
  fail "Run as root on tracker-dev"
[[ -x "$PY" ]] || fail "Configured Python missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] ||
  fail "Require clean installed DEV main"
[[ "$(git rev-parse HEAD)" == "$BASE" ]] ||
  fail "Require installed DEV Release 687"
git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(git rev-parse "refs/remotes/origin/$REF")"
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Candidate not based on Release 687"
RUN="$(mktemp -d /tmp/tracker-688-preview.XXXXXXXX)"
QA="$RUN/source"
cleanup(){
 code=$?
 trap - EXIT
 if [[ -d "$QA" ]]; then git -C "$APP" worktree remove --force "$QA" >/dev/null 2>&1 || true; fi
 rm -rf -- "$RUN"
 echo "RELEASE_688_PREVIEW_EXIT_STATUS=$code"
 exit "$code"
}
trap cleanup EXIT
git worktree add --detach "$QA" "$TARGET"
export GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP" GIT_CONFIG_KEY_1=safe.directory GIT_CONFIG_VALUE_1="$QA"
export PYTHONPATH="$QA" TRACKER_DATA_DIR="$RUN/test-data"
mkdir -p "$TRACKER_DATA_DIR"
cd "$QA"
git diff --check "$BASE" "$TARGET"
EXPECTED="$(printf '%s\n' \
  app/static/css/tracker-dashboard-polish688.css \
  app/templates/base.html \
  app/templates/dashboard.html \
  app/templates/_workout_dashboard661.html \
  tests/test_dashboard_polish688.py \
  tests/test_workout_activity_cards_browser678.py \
  scripts/tracker-preview688.sh \
  scripts/tracker-release-scoped688.sh | LC_ALL=C sort)"
ACTUAL="$(git diff --name-only "$BASE" "$TARGET" | LC_ALL=C sort)"
[[ "$ACTUAL" == "$EXPECTED" ]] || fail "Unexpected source file modifications"
"$PY" scripts/tracker-impact-preflight604.py --base "$BASE" --target "$TARGET" --root "$QA"
bash scripts/tracker-release-scoped688.sh "$PY"
echo "RELEASE_688_PREVIEW_QUALIFIED=$TARGET"
echo "RELEASE_688_PREVIEW=PASSED_ISOLATED_NO_INSTALL"
