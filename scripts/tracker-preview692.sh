#!/usr/bin/env bash
# Release 692: isolated, exact-manifest Workout scanner removal preview only.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=869ada02eb9ac523ca9e8ce7c19ed6b92b303d68
REF=release/692-remove-workout-qr-camera
fail(){ echo "RELEASE_692_PREVIEW_ERROR=$*" >&2; exit 1; }
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev &&
   -n "$(printenv INVOCATION_ID || true)" ]] || fail "Detached root systemd service on tracker-dev required"
[[ -x "$PY" ]] || fail "Configured Python missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main && -z "$(git status --porcelain)" ]] ||
  fail "Require clean DEV main"
[[ "$(git rev-parse HEAD)" == "$BASE" ]] || fail "Require installed DEV Release 691"
systemctl is-active --quiet tracker || fail "DEV Tracker service inactive"
git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(git rev-parse "refs/remotes/origin/$REF")"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Target not descendant of 691"
QA_ROOT="$(mktemp -d /tmp/tracker-preview692.XXXXXXXX)"
QA="$QA_ROOT/source"
cleanup(){
  rc=$?
  trap - EXIT
  if [[ -d "$QA" ]]; then git -C "$APP" worktree remove --force "$QA" >/dev/null 2>&1 || true; fi
  rm -rf -- "$QA_ROOT"
  echo "RELEASE_692_PREVIEW_EXIT_STATUS=$rc"
  exit "$rc"
}
trap cleanup EXIT
git worktree add --detach "$QA" "$TARGET"
export GIT_CONFIG_COUNT=2 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP" GIT_CONFIG_KEY_1=safe.directory GIT_CONFIG_VALUE_1="$QA"
export PYTHONPATH="$QA" TRACKER_DATA_DIR="$QA_ROOT/test-data"
mkdir -p "$TRACKER_DATA_DIR"
cd "$QA"
git diff --check "$BASE" "$TARGET"
"$PY" scripts/tracker-workout-camera-review692.py --root "$QA" --base "$BASE" --target "$TARGET"
"$PY" scripts/tracker-impact-preflight604.py --base "$BASE" --target "$TARGET" --root "$QA"
bash scripts/tracker-release-scoped692.sh "$PY"
echo "RELEASE_692_PREVIEW_QUALIFIED=$TARGET"
echo "RELEASE_692_PREVIEW=PASSED_ISOLATED_NO_INSTALL"
