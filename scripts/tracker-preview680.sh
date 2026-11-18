#!/usr/bin/env bash
# Release 680: no-install, isolated candidate qualification on tracker-dev.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
REF=release/680-explanation-touch-targets
BASE=a24bb47e0193ce7ca61b6d095ab055f37082aaf7
PY="$APP/.venv/bin/python"
die(){ echo "RELEASE_680_PREVIEW_ERROR=$*" >&2; exit 1; }
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] || die "Root on tracker-dev required"
[[ -x "$PY" ]] || die "Configured Python missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] || die "DEV checkout must be clean main"
[[ "$(git rev-parse HEAD)" == "$BASE" ]] || die "Installed DEV baseline is not Release 679"
git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(git rev-parse "refs/remotes/origin/$REF")"
[[ "$TARGET" =~ ^[0-9a-f]{40}$ ]] || die "Invalid target"
git merge-base --is-ancestor "$BASE" "$TARGET" || die "Not descended from baseline"
ROOT="$(mktemp -d /tmp/tracker-680-preview.XXXXXXXX)"
QA="$ROOT/source"
cleanup(){
 code=$?
 trap - EXIT
 if [[ -d "$QA" ]]; then git -C "$APP" worktree remove --force "$QA" >/dev/null 2>&1 || true; fi
 rm -rf -- "$ROOT"
 echo "RELEASE_680_PREVIEW_EXIT_STATUS=$code"
 exit "$code"
}
trap cleanup EXIT
git worktree add --detach "$QA" "$TARGET"
export GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP" GIT_CONFIG_KEY_1=safe.directory GIT_CONFIG_VALUE_1="$QA"
export PYTHONPATH="$QA" TRACKER_DATA_DIR="$ROOT/isolated-data"
mkdir -p "$TRACKER_DATA_DIR"
cd "$QA"
git diff --check "$BASE" "$TARGET"
EXPECTED="$(printf '%s\n' \
 app/static/css/tracker-explanation-touch680.css \
 app/templates/base.html \
 tests/test_explanation_touch680.py \
 scripts/tracker-release-scoped680.sh \
 scripts/tracker-preview680.sh | LC_ALL=C sort)"
ACTUAL="$(git diff --name-only "$BASE" "$TARGET" | LC_ALL=C sort)"
[[ "$EXPECTED" == "$ACTUAL" ]] || die "Unexpected change set"
bash scripts/tracker-release-scoped680.sh "$PY"
echo "RELEASE_680_PREVIEW_QUALIFIED=$TARGET"
echo "RELEASE_680_PREVIEW=PASSED_ISOLATED_NO_INSTALL"
