#!/usr/bin/env bash
# Staged Workout 654–657: streamed from qualified DEV via BatchMode SSH, never installed on PROD.
set -Eeuo pipefail
umask 077

APP=/opt/tracker
ROOT=/etc/tracker-release
fail() { echo "REMOTE_FAIL: $*" >&2; exit 1; }
STAGE=""
trap 'rc=$?; if [[ -n "$STAGE" ]]; then rm -f -- "$STAGE/runner.sh" || true; rmdir -- "$STAGE" || true; fi; echo "REMOTE_DEPLOY_EXIT_STATUS=$rc"' EXIT

[[ $# -eq 3 ]] || fail "Expected exact base, target and release"
BASE="$1"
TARGET="$2"
RELEASE="$3"
[[ "$BASE" =~ ^[0-9a-f]{40}$ && "$TARGET" =~ ^[0-9a-f]{40}$ ]] ||
  fail "Invalid commit identifier"
[[ "$RELEASE" =~ ^[1-9][0-9]{0,5}$ ]] || fail "Invalid release number"

case "$RELEASE:$BASE:$TARGET" in
  "654:108bf3241bd747f6174dc7e65a8c01161af24e62:419e0c199d6a5dc373df7de1401953a056cac8d1") ;;
  "655:419e0c199d6a5dc373df7de1401953a056cac8d1:b1d8ad1d3003d1f8ef2e5b3614ba1148076c5c25") ;;
  "656:b1d8ad1d3003d1f8ef2e5b3614ba1148076c5c25:06b8be62f5be455df47be87bc5157b41fcac8783") ;;
  "657:06b8be62f5be455df47be87bc5157b41fcac8783:b9487d4b1fab176255b398833c51c9a2da79f042") ;;
  *) fail "Unapproved staged Workout release, base or target" ;;
esac
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

# PROD still has the previous release installed. Never invoke its local
# deployment runner. Extract the exact Git object from the signed target,
# before any installed source or data is changed.
EXPECTED_RUNNER="$(git rev-parse "$TARGET:scripts/tracker-release.sh")" ||
  fail "Signed target has no deployment runner"
[[ "$EXPECTED_RUNNER" =~ ^[0-9a-f]{40}$ ]] || fail "Invalid target runner blob"
STAGE="$(mktemp -d /tmp/tracker-prod-runner.XXXXXXXX)" ||
  fail "Unable to stage target runner"
chmod 700 "$STAGE"
RUNNER="$STAGE/runner.sh"
git show "$TARGET:scripts/tracker-release.sh" > "$RUNNER" ||
  fail "Unable to extract signed target runner"
[[ -f "$RUNNER" && ! -L "$RUNNER" ]] || fail "Unsafe staged runner"
[[ "$(git hash-object "$RUNNER")" == "$EXPECTED_RUNNER" ]] ||
  fail "Staged runner does not match signed target Git blob"
bash -n "$RUNNER" || fail "Signed runner has invalid shell syntax"
echo "PROD_PINNED_RUNNER_BLOB=$EXPECTED_RUNNER"

: > "$LOG"
chmod 600 "$LOG"
# Exact-target guarded runner owns backups, backend tests, approval
# verification, fast-forward, runtime checks and rollback.
DEPLOY_EXTRA=()
if [[ "$RELEASE" == 635 ]]; then
  DEPLOY_EXTRA=(--reviewed-regimen-635 --db-migration)
elif [[ "$RELEASE" == 639 || "$RELEASE" == 640 ]]; then
  DEPLOY_EXTRA=(--reviewed-facts-639 --db-migration)
elif [[ "$RELEASE" == 643 || "$RELEASE" == 644 ]]; then
  DEPLOY_EXTRA=(--reviewed-coa-643 --db-migration)
elif [[ "$RELEASE" == 645 ]]; then
  DEPLOY_EXTRA=(--reviewed-coa-645 --db-migration)
elif [[ "$RELEASE" == 652 ]]; then
  DEPLOY_EXTRA=(--reviewed-coa-652 --db-migration)
elif [[ "$RELEASE" == 654 ]]; then
  DEPLOY_EXTRA=(--reviewed-workout-654 --db-migration)
elif [[ "$RELEASE" == 655 ]]; then
  DEPLOY_EXTRA=(--reviewed-workout-655 --db-migration)
fi
bash "$RUNNER" \
  --instance PROD \
  --base "$BASE" \
  --target "$TARGET" \
  --ref main "${DEPLOY_EXTRA[@]}" 2>&1 | tee "$LOG"

[[ "$(git rev-parse HEAD)" == "$TARGET" ]] ||
  fail "Final PROD checkout does not match target"
systemctl is-active --quiet tracker ||
  fail "PROD Tracker inactive after deployment"
grep -Fq 'TRACKER RELEASE DEPLOYMENT SUCCESS' "$LOG" ||
  fail "Guarded deployment success marker missing"
grep -Fxq 'EXIT_STATUS=0' "$LOG" ||
  fail "Guarded deployment exit status missing"

echo "PROD_DEPLOY_VERIFIED=$TARGET"
