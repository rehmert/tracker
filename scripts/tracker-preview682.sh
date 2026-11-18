#!/usr/bin/env bash
# Release 682: isolated, change-scoped preview; no install.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
BASE=893b78db3a83fb16db54c3850a6b660f03611a6c
REF=release/682-overview-css-order
PY="$APP/.venv/bin/python"
fail(){ echo "RELEASE_682_PREVIEW_ERROR=$*" >&2; exit 1; }
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] || fail "Root on tracker-dev required"
[[ -x "$PY" ]] || fail "Configured Python missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] || fail "Require clean main"
[[ "$(git rev-parse HEAD)" == "$BASE" ]] || fail "DEV baseline must be installed Release 681"
git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(git rev-parse "refs/remotes/origin/$REF")"
[[ "$TARGET" =~ ^[0-9a-f]{40}$ ]] || fail "Invalid target"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Target not descended from baseline"
ROOT="$(mktemp -d /tmp/tracker-682-preview.XXXXXXXX)"
QA="$ROOT/source"
cleanup(){
 code=$?
 trap - EXIT
 if [[ -d "$QA" ]]; then git -C "$APP" worktree remove --force "$QA" >/dev/null 2>&1 || true; fi
 rm -rf -- "$ROOT"
 echo "RELEASE_682_PREVIEW_EXIT_STATUS=$code"
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
 app/templates/dashboard.html \
 tests/test_overview_css_order682.py \
 scripts/tracker-release-scoped682.sh \
 scripts/tracker-preview682.sh | LC_ALL=C sort)"
ACTUAL="$(git diff --name-only "$BASE" "$TARGET" | LC_ALL=C sort)"
[[ "$ACTUAL" == "$EXPECTED" ]] || fail "Unexpected change set"
bash scripts/tracker-release-scoped682.sh "$PY"
echo "RELEASE_682_PREVIEW_QUALIFIED=$TARGET"
echo "RELEASE_682_PREVIEW=PASSED_ISOLATED_NO_INSTALL"
