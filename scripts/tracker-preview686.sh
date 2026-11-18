#!/usr/bin/env bash
# Release 686: pinned isolated preview; no app installation or PROD access.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
BASE=481b105d55a916b5d3067a51076bb679a48142d9
REF=release/686-compact-spacing
PY="$APP/.venv/bin/python"
fail(){ echo "RELEASE_686_PREVIEW_ERROR=$*" >&2; exit 1; }
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] || fail "Run as root on tracker-dev"
[[ -x "$PY" ]] || fail "Configured Python executable unavailable"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] || fail "Require clean DEV main"
[[ "$(git rev-parse HEAD)" == "$BASE" ]] || fail "DEV must be installed Release 685"
git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(git rev-parse "refs/remotes/origin/$REF")"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Candidate not descendant of Release 685"
ROOT="$(mktemp -d /tmp/tracker-686-preview.XXXXXXXX)"
QA="$ROOT/source"
cleanup(){
 code=$?
 trap - EXIT
 if [[ -d "$QA" ]]; then git -C "$APP" worktree remove --force "$QA" >/dev/null 2>&1 || true; fi
 rm -rf -- "$ROOT"
 echo "RELEASE_686_PREVIEW_EXIT_STATUS=$code"
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
 app/static/css/tracker-compact-aggressive686.css \
 app/templates/base.html \
 scripts/tracker-preview686.sh \
 scripts/tracker-release-scoped686.sh \
 tests/test_compact_spacing686.py | LC_ALL=C sort)"
ACTUAL="$(git diff --name-only "$BASE" "$TARGET" | LC_ALL=C sort)"
[[ "$ACTUAL" == "$EXPECTED" ]] || fail "Unexpected modified files"
"$PY" scripts/tracker-impact-preflight604.py --base "$BASE" --target "$TARGET" --root "$QA"
bash scripts/tracker-release-scoped686.sh "$PY"
echo "RELEASE_686_PREVIEW_QUALIFIED=$TARGET"
echo "RELEASE_686_PREVIEW=PASSED_ISOLATED_NO_INSTALL"
