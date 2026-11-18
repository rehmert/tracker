#!/usr/bin/env bash
# Release 687: isolated preview only (does not install onto DEV or PROD).
set -Eeuo pipefail
umask 077
APP=/opt/tracker
BASE=6d6505403ec191df66977ea0fab9d1004f7a022f
REF=release/687-shortcuts-toolbar
PY="$APP/.venv/bin/python"
fail(){ echo "RELEASE_687_PREVIEW_ERROR=$*" >&2; exit 1; }
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] || fail "Run as root on tracker-dev"
[[ -x "$PY" ]] || fail "Configured Python unavailable"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] || fail "DEV main must be clean"
[[ "$(git rev-parse HEAD)" == "$BASE" ]] || fail "DEV must have Release 686 installed"
git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(git rev-parse "refs/remotes/origin/$REF")"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Candidate is not descendant of Release 686"
STAGE="$(mktemp -d /tmp/tracker-687-preview.XXXXXXXX)"
QA="$STAGE/source"
cleanup(){
 code=$?
 trap - EXIT
 if [[ -d "$QA" ]]; then git -C "$APP" worktree remove --force "$QA" >/dev/null 2>&1 || true; fi
 rm -rf -- "$STAGE"
 echo "RELEASE_687_PREVIEW_EXIT_STATUS=$code"
 exit "$code"
}
trap cleanup EXIT
git worktree add --detach "$QA" "$TARGET"
export GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP" GIT_CONFIG_KEY_1=safe.directory GIT_CONFIG_VALUE_1="$QA"
export PYTHONPATH="$QA" TRACKER_DATA_DIR="$STAGE/test-data"
mkdir -p "$TRACKER_DATA_DIR"
cd "$QA"
git diff --check "$BASE" "$TARGET"
EXPECTED="$(printf '%s\n' \
 app/static/css/tracker-shortcuts-toolbar687.css \
 app/templates/base.html \
 scripts/tracker-preview687.sh \
 scripts/tracker-release-scoped687.sh \
 tests/test_shortcuts_toolbar687.py | LC_ALL=C sort)"
ACTUAL="$(git diff --name-only "$BASE" "$TARGET" | LC_ALL=C sort)"
[[ "$ACTUAL" == "$EXPECTED" ]] || fail "Unexpected source changes"
"$PY" scripts/tracker-impact-preflight604.py --base "$BASE" --target "$TARGET" --root "$QA"
bash scripts/tracker-release-scoped687.sh "$PY"
echo "RELEASE_687_PREVIEW_QUALIFIED=$TARGET"
echo "RELEASE_687_PREVIEW=PASSED_ISOLATED_NO_INSTALL"
