#!/usr/bin/env bash
# Release 689: isolated, exact-manifest preview; no installation.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
BASE=a55456b3c9e74e91dc35a7cd74579566c7a63355
REF=release/689-workout-footnote-spacing
PY="$APP/.venv/bin/python"
fail(){ echo "RELEASE_689_PREVIEW_ERROR=$*" >&2; exit 1; }
[[ -n "${INVOCATION_ID:-}" ]] || fail "Foreground preview refused"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] ||
  fail "Run as root on tracker-dev"
[[ -x "$PY" ]] || fail "Configured Python missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] ||
  fail "Require clean installed DEV main"
[[ "$(git rev-parse HEAD)" == "$BASE" ]] ||
  fail "Require installed DEV Release 688"
git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(git rev-parse "refs/remotes/origin/$REF")"
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Candidate not based on Release 688"
RUN="$(mktemp -d /tmp/tracker-689-preview.XXXXXXXX)"
QA="$RUN/source"
cleanup(){
 code=$?
 trap - EXIT
 if [[ -d "$QA" ]]; then git -C "$APP" worktree remove --force "$QA" >/dev/null 2>&1 || true; fi
 rm -rf -- "$RUN"
 echo "RELEASE_689_PREVIEW_EXIT_STATUS=$code"
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
  app/static/css/tracker-workout-footnote689.css \
  app/templates/base.html \
  scripts/tracker-preview689.sh \
  scripts/tracker-release-scoped689.sh \
  tests/test_workout_footnote_spacing689.py | LC_ALL=C sort)"
ACTUAL="$(git diff --name-only "$BASE" "$TARGET" | LC_ALL=C sort)"
[[ "$ACTUAL" == "$EXPECTED" ]] || fail "Unexpected source file modifications"
"$PY" scripts/tracker-impact-preflight604.py --base "$BASE" --target "$TARGET" --root "$QA"
bash scripts/tracker-release-scoped689.sh "$PY"
echo "RELEASE_689_PREVIEW_QUALIFIED=$TARGET"
echo "RELEASE_689_PREVIEW=PASSED_ISOLATED_NO_INSTALL"
