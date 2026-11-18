#!/usr/bin/env bash
# Release 684: isolated DEV preview of visible vendor/lot picker, no install.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
BASE=743a6c4d40fb6668e2cc264217fb299a6d746d69
REF=release/684-reconstitution-vial-picker-visible
PY="$APP/.venv/bin/python"
fail(){ echo "RELEASE_684_PREVIEW_ERROR=$*" >&2; exit 1; }
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] || fail "Run as root on tracker-dev"
[[ -x "$PY" ]] || fail "Configured Python missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] || fail "Require clean installed checkout"
[[ "$(git rev-parse HEAD)" == "$BASE" ]] || fail "DEV must be installed Release 683"
git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(git rev-parse "refs/remotes/origin/$REF")"
[[ "$TARGET" =~ ^[0-9a-f]{40}$ ]] || fail "Invalid target"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Candidate not descendant of Release 683"
ROOT="$(mktemp -d /tmp/tracker-684-preview.XXXXXXXX)"
QA="$ROOT/source"
cleanup(){
 code=$?
 trap - EXIT
 if [[ -d "$QA" ]]; then git -C "$APP" worktree remove --force "$QA" >/dev/null 2>&1 || true; fi
 rm -rf -- "$ROOT"
 echo "RELEASE_684_PREVIEW_EXIT_STATUS=$code"
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
 app/templates/reconstitution_calculator.html \
 app/static/css/reconstitution-calculator.css \
 tests/test_reconstitution_picker684.py \
 scripts/tracker-release-scoped684.sh \
 scripts/tracker-preview684.sh | LC_ALL=C sort)"
ACTUAL="$(git diff --name-only "$BASE" "$TARGET" | LC_ALL=C sort)"
[[ "$ACTUAL" == "$EXPECTED" ]] || fail "Unexpected source changes"
"$PY" scripts/tracker-impact-preflight604.py --base "$BASE" --target "$TARGET" --root "$QA"
bash scripts/tracker-release-scoped684.sh "$PY"
echo "RELEASE_684_PREVIEW_QUALIFIED=$TARGET"
echo "RELEASE_684_PREVIEW=PASSED_ISOLATED_NO_INSTALL"
