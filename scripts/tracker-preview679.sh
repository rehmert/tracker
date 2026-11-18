#!/usr/bin/env bash
# DEV-hosted Release 679 preview. No install or production access.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
REF=release/679-ui-foundation
BASE=b0a40f02837b6221b9d9474bdc74ac6a7c7835b0
PY="$APP/.venv/bin/python"
fail() { echo "RELEASE_679_PREVIEW_ERROR=$*" >&2; exit 1; }
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] ||
  fail "Root on tracker-dev required"
[[ -x "$PY" ]] || fail "Configured Python missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] ||
  fail "DEV must be a clean main checkout"
git fetch origin main "refs/heads/$REF:refs/remotes/origin/$REF"
[[ "$(git rev-parse HEAD)" == "$BASE" && "$(git rev-parse origin/main)" == "$BASE" ]] ||
  fail "DEV baseline/main mismatch; re-evaluate before proceeding"
TARGET="$(git rev-parse "refs/remotes/origin/$REF")"
[[ "$TARGET" =~ ^[0-9a-f]{40}$ ]] || fail "Invalid candidate commit"
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Candidate must descend from Release 678"
ROOT="$(mktemp -d /tmp/tracker-679-preview.XXXXXXXX)"
chmod 700 "$ROOT"
QA="$ROOT/source"
cleanup679() {
  code=$?
  trap - EXIT
  if [[ -d "$QA" ]]; then
    git -C "$APP" worktree remove --force "$QA" || true
  fi
  rm -rf -- "$ROOT"
  echo "RELEASE_679_PREVIEW_EXIT_STATUS=$code"
  exit "$code"
}
trap cleanup679 EXIT
git worktree add --detach "$QA" "$TARGET"
export GIT_CONFIG_COUNT=2
export GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
export GIT_CONFIG_KEY_1=safe.directory GIT_CONFIG_VALUE_1="$QA"
export TRACKER_DATA_DIR="$ROOT/isolated-data"
export PYTHONPATH="$QA"
mkdir -p "$TRACKER_DATA_DIR"
cd "$QA"
git diff --check "$BASE" "$TARGET"
# 679 preview is intentionally code, templates, tests, scripts, documentation only.
if git diff --name-only "$BASE" "$TARGET" |
  grep -Eq '^(app/(db|models|migrations|scoped_db|auth|security|csrf|session_auth|food_storage_guard)|alembic/|requirements[^/]*|deploy/)'; then
  fail "Candidate modifies schema/security/dependencies; requires separate review"
fi
bash scripts/tracker-release-scoped679.sh "$PY"
echo "RELEASE_679_PREVIEW_QUALIFIED=$TARGET"
echo "RELEASE_679_PREVIEW=PASSED_ISOLATED_NO_INSTALL"
