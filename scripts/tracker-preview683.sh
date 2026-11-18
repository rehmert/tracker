#!/usr/bin/env bash
# Release 683: isolated, DEV-baseline-pinned preview; no installation.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
BASE=bacea46bd00564c35c3f129c2f71c28b8558fb71
REF=release/683-reconstitution-workflow
PY="$APP/.venv/bin/python"
fail(){ echo "RELEASE_683_PREVIEW_ERROR=$*" >&2; exit 1; }
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] || fail "Run as root on tracker-dev"
[[ -x "$PY" ]] || fail "Configured Python missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] || fail "Require clean main checkout"
[[ "$(git rev-parse HEAD)" == "$BASE" ]] || fail "DEV baseline differs from Release 682"
git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(git rev-parse "refs/remotes/origin/$REF")"
[[ "$TARGET" =~ ^[0-9a-f]{40}$ ]] || fail "Invalid target"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Candidate not descendant of Release 682"
ROOT="$(mktemp -d /tmp/tracker-683-preview.XXXXXXXX)"
QA="$ROOT/source"
cleanup(){
 code=$?
 trap - EXIT
 if [[ -d "$QA" ]]; then git -C "$APP" worktree remove --force "$QA" >/dev/null 2>&1 || true; fi
 rm -rf -- "$ROOT"
 echo "RELEASE_683_PREVIEW_EXIT_STATUS=$code"
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
 app/routers/reconstitution_calculator.py \
 app/routers/vials.py \
 app/templates/reconstitution_calculator.html \
 app/templates/vial_detail.html \
 tests/test_reconstitution_workflow683.py \
 scripts/tracker-release-scoped683.sh \
 scripts/tracker-preview683.sh | LC_ALL=C sort)"
ACTUAL="$(git diff --name-only "$BASE" "$TARGET" | LC_ALL=C sort)"
[[ "$ACTUAL" == "$EXPECTED" ]] || fail "Unexpected candidate change set"
bash scripts/tracker-release-scoped683.sh "$PY"
echo "RELEASE_683_PREVIEW_QUALIFIED=$TARGET"
echo "RELEASE_683_PREVIEW=PASSED_ISOLATED_NO_INSTALL"
