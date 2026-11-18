#!/usr/bin/env bash
# Release 685: isolated preview only; no DEV/PROD installation or data mutations.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
BASE=b42b39cb9f490325358a9a7ddc305ac7ca6ed5fb
REF=release/685-layout-density
PY="$APP/.venv/bin/python"
fail(){ echo "RELEASE_685_PREVIEW_ERROR=$*" >&2; exit 1; }
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] || fail "Run as root on tracker-dev"
[[ -x "$PY" ]] || fail "Configured Python missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] || fail "DEV checkout must be clean main"
[[ "$(git rev-parse HEAD)" == "$BASE" ]] || fail "DEV must have Release 684 installed"
git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(git rev-parse "refs/remotes/origin/$REF")"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Release not descended from DEV 684"
ROOT="$(mktemp -d /tmp/tracker-685-preview.XXXXXXXX)"
QA="$ROOT/source"
cleanup(){
 code=$?
 trap - EXIT
 if [[ -d "$QA" ]]; then git -C "$APP" worktree remove --force "$QA" >/dev/null 2>&1 || true; fi
 rm -rf -- "$ROOT"
 echo "RELEASE_685_PREVIEW_EXIT_STATUS=$code"
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
  app/static/css/tracker-layout-density685.css \
  app/templates/base.html \
  tests/test_layout_density685.py \
  scripts/tracker-release-scoped685.sh \
  scripts/tracker-preview685.sh | LC_ALL=C sort)"
ACTUAL="$(git diff --name-only "$BASE" "$TARGET" | LC_ALL=C sort)"
[[ "$ACTUAL" == "$EXPECTED" ]] || fail "Unexpected changed files"
"$PY" scripts/tracker-impact-preflight604.py --base "$BASE" --target "$TARGET" --root "$QA"
bash scripts/tracker-release-scoped685.sh "$PY"
echo "RELEASE_685_PREVIEW_QUALIFIED=$TARGET"
echo "RELEASE_685_PREVIEW=PASSED_ISOLATED_NO_INSTALL"
