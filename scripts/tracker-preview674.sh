#!/usr/bin/env bash
# Isolated DEV-only Release 674 integrated productivity qualification.
# Does not install the release, change /opt/tracker/main, or deploy PROD.
# GitHub is source storage only. Never requires hosted CI.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
REF=release/674-integrated-productivity
PY="$APP/.venv/bin/python"
fail() { echo "RELEASE_674_PREVIEW_ERROR=$*" >&2; exit 1; }
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] ||
  fail "Root on tracker-dev required"
[[ -x "$PY" ]] || fail "Configured Python missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] ||
  fail "DEV must be a clean main checkout"
git fetch origin main "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(git rev-parse "refs/remotes/origin/$REF")"
[[ "$TARGET" =~ ^[0-9a-f]{40}$ ]] || fail "Invalid branch SHA"
git merge-base --is-ancestor origin/main "$TARGET" ||
  fail "Candidate must descend from main"
ROOT="$(mktemp -d /tmp/tracker-674-preview.XXXXXXXX)"
chmod 700 "$ROOT"
QA="$ROOT/source"
cleanup674() {
  code=$?
  trap - EXIT
  if [[ -d "$QA" ]]; then
    git -C "$APP" worktree remove --force "$QA" || true
  fi
  rm -rf -- "$ROOT"
  echo "RELEASE_674_PREVIEW_EXIT_STATUS=$code"
  exit "$code"
}
trap cleanup674 EXIT
git worktree add --detach "$QA" "$TARGET"
export GIT_CONFIG_COUNT=2
export GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
export GIT_CONFIG_KEY_1=safe.directory GIT_CONFIG_VALUE_1="$QA"
export TRACKER_DATA_DIR="$ROOT/isolated-data"
export PYTHONPATH="$QA"
mkdir -p "$TRACKER_DATA_DIR"
cd "$QA"
git diff --check "$(git -C "$APP" rev-parse origin/main)" "$TARGET"
bash scripts/tracker-release-scoped674.sh "$PY"
echo "RELEASE_674_PREVIEW_QUALIFIED=$TARGET"
echo "RELEASE_674_PREVIEW=PASSED_ISOLATED_NO_INSTALL"
