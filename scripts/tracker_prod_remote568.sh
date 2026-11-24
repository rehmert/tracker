#!/usr/bin/env bash
# Streamed from qualified DEV over BatchMode SSH. Never required on old PROD.
set -Eeuo pipefail
umask 077

APP=/opt/tracker
ROOT=/etc/tracker-release
fail() { echo "REMOTE_FAIL: $*" >&2; exit 1; }
STAGE=""
trap 'rc=$?; if [[ -n "$STAGE" ]]; then rm -f -- "$STAGE/runner.sh" "$STAGE/pre-schema-backup767.py" || true; rmdir -- "$STAGE" || true; fi; echo "REMOTE_DEPLOY_EXIT_STATUS=$rc"' EXIT

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
elif [[ "$RELEASE" == 667 ]]; then
  # Signed Release 667 is an additive schema change; do not bypass backup.
  DEPLOY_EXTRA=(--reviewed-workout-667 --db-migration)
elif [[ "$RELEASE" == 668 ]]; then
  # New additive Workout tables require signed exact-source review and backup.
  DEPLOY_EXTRA=(--reviewed-workout-668 --db-migration)
elif [[ "$RELEASE" == 691 ]]; then
  # Each COA document gets two additive identifier columns. Enforce reviewed
  # exact-source schema checks and verified SQLite + uploads backup on PROD.
  DEPLOY_EXTRA=(--reviewed-coa-691 --db-migration)
elif [[ "$RELEASE" == 735 ]]; then
  # One-time 727 -> 735 catch-up includes the reviewed 731 additive schema.
  # The signed worker independently repeats exact-schema proof and performs
  # a verified database + attachment backup before installation.
  [[ "$BASE" == 3718936aedfcb1b8fe243c86fe6fc7e06a7a41d2 ]] ||
    fail "Release 735 catch-up requires exact PROD 727 base"
  DEPLOY_EXTRA=(--reviewed-catchup-735 --db-migration)
elif [[ "$RELEASE" == 710 ]]; then
  # One prepared physical blend in the standard dose form; four additive
  # fields and a supply index require exact-source review and verified backup.
  DEPLOY_EXTRA=(--reviewed-blend-710 --db-migration)
elif [[ "$RELEASE" == 763 ]]; then
  # PROD's installed Release 761 lacks the five additive progress tables.
  # Explicit exact-schema review and verified SQLite + upload backup required.
  [[ "$BASE" == 04fd141daa17fd2055f9177527296eb9165a59d2 ]] ||
    fail "Release 763 progress schema catch-up requires installed PROD 761"
  DEPLOY_EXTRA=(--reviewed-progress-762 --db-migration)
elif [[ "$RELEASE" == 760 ]]; then
  # PROD 755 catch-up includes the exact reviewed nullable Release 758
  # manufacturing-date addition; pin the old PROD commit and require a
  # verified backup and independent exact-additive source review.
  [[ "$BASE" == bb83f1a59de3defd5fe6d0bc83ad09ed4d0cfdac ]] ||
    fail "Release 760 schema catch-up requires exact installed PROD 755 base"
  DEPLOY_EXTRA=(--reviewed-vial-758 --db-migration)
fi
# 767 promotes the already-qualified 766 data model. Its new independent
# module is not covered by the older runner's schema-file allowlist.
# Before any source installation, enforce an exact-reviewed additive schema,
# strict present-upload integrity, a complete private database/upload archive,
# and isolated restore verification. Never treat normal code-only release
# backups as a substitute for this migration barrier.
if [[ "$RELEASE" == 767 ]]; then
  [[ "$BASE" == 8c67580611fd945d9ae83f8015f071a24ab6fee5 ]] ||
    fail "Release 767 requires exact installed PROD Release 765 baseline"
  BACKUP_REL=scripts/tracker-prod-schema-backup767.py
  EXPECTED_BACKUP="$(git rev-parse "$TARGET:$BACKUP_REL")" ||
    fail "Signed Release 767 backup guard missing"
  [[ "$EXPECTED_BACKUP" =~ ^[0-9a-f]{40}$ ]] ||
    fail "Invalid Release 767 backup-guard object"
  BACKUP_GUARD="$STAGE/pre-schema-backup767.py"
  git show "$TARGET:$BACKUP_REL" > "$BACKUP_GUARD" ||
    fail "Unable to stage signed schema/backup guard"
  [[ -f "$BACKUP_GUARD" && ! -L "$BACKUP_GUARD" &&
    "$(git hash-object "$BACKUP_GUARD")" == "$EXPECTED_BACKUP" ]] ||
    fail "Pinned Release 767 backup-guard integrity mismatch"
  PYTHONPATH="$APP" "$APP/.venv/bin/python" "$BACKUP_GUARD" \
    --app "$APP" --base "$BASE" --target "$TARGET" ||
    fail "Release 767 PROD schema review or verified pre-install backup failed"
  echo "RELEASE_767_PROD_SCHEMA_BACKUP=PASSED"
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
