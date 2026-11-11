#!/usr/bin/env bash
# Streamed from qualified DEV over BatchMode SSH. Never required on old PROD.
set -Eeuo pipefail
umask 077

APP=/opt/tracker
ROOT=/etc/tracker-release
fail() { echo "REMOTE_FAIL: $*" >&2; exit 1; }
trap 'rc=$?; echo "REMOTE_DEPLOY_EXIT_STATUS=$rc"' EXIT

[[ $# -eq 3 ]] || fail "Expected exact base, target and release"
BASE="$1"
TARGET="$2"
RELEASE="$3"
[[ "$BASE" =~ ^[0-9a-f]{40}$ && "$TARGET" =~ ^[0-9a-f]{40}$ ]] ||
  fail "Invalid commit identifier"
[[ "$RELEASE" =~ ^[1-9][0-9]{0,5}$ ]] || fail "Invalid release number"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-prod ]] ||
  fail "Run as root on tracker-prod"

export GIT_CONFIG_COUNT=1
export GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP"
cd "$APP"

echo "========================================"
echo " TRACKER RELEASE $RELEASE - REMOTE PROD"
echo "========================================"

[[ "$(git branch --show-current)" == main ]] ||
  fail "PROD branch is not main"
[[ -z "$(git status --porcelain)" ]] ||
  fail "PROD checkout has uncommitted changes"
systemctl is-active --quiet tracker || fail "PROD Tracker is inactive"

git fetch origin main
[[ "$(git rev-parse origin/main)" == "$TARGET" ]] ||
  fail "GitHub main differs from signed target"
git merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Target not descended from expected PROD base"

/usr/local/sbin/tracker-verify-dev-approval "$TARGET" ||
  fail "PROD rejected DEV approval signature"

HEAD="$(git rev-parse HEAD)"
LOG="$ROOT/release-$RELEASE-prod.log"
[[ ! -L "$LOG" ]] || fail "Unsafe production log path"
[[ -d "$ROOT" && ! -L "$ROOT" ]] || fail "Unsafe release directory"

if [[ "$HEAD" == "$TARGET" ]]; then
  [[ -f "$LOG" && ! -L "$LOG" ]] ||
    fail "Already installed but deployment log unavailable"
  grep -Fq 'TRACKER RELEASE DEPLOYMENT SUCCESS' "$LOG" ||
    fail "Already installed but success evidence missing"
  grep -Fxq 'EXIT_STATUS=0' "$LOG" ||
    fail "Already installed but exit-status evidence missing"
  echo "PROD_ALREADY_DEPLOYED=$TARGET"
  exit 0
fi
[[ "$HEAD" == "$BASE" ]] || fail "Unexpected installed PROD commit"

: > "$LOG"
chmod 600 "$LOG"
# Existing guarded runner owns backups, parallel backend tests, signed
# approval verification, fast-forward, runtime checks and rollback.
bash scripts/tracker-release.sh \
  --instance PROD \
  --base "$BASE" \
  --target "$TARGET" \
  --ref main 2>&1 | tee "$LOG"

[[ "$(git rev-parse HEAD)" == "$TARGET" ]] ||
  fail "Final PROD checkout does not match target"
systemctl is-active --quiet tracker ||
  fail "PROD Tracker inactive after deployment"
grep -Fq 'TRACKER RELEASE DEPLOYMENT SUCCESS' "$LOG" ||
  fail "Guarded deployment success marker missing"
grep -Fxq 'EXIT_STATUS=0' "$LOG" ||
  fail "Guarded deployment exit status missing"

echo "PROD_DEPLOY_VERIFIED=$TARGET"
