#!/usr/bin/env bash
# Release 693: guarded detached DEV-only controlled PROD rollout.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY=/opt/tracker/.venv/bin/python
BASE=696fe7f482436090df5342f76cd65b9fb5febad4
TARGET=4d752be1a62ffa8a5feba78a50033e980a30b26c
REF=release/693-retire-workout-qr-mapping-ui
STAGE=
PAUSED=0
fail(){ echo "RELEASE_693_ROLLOUT_ERROR=$*" >&2; exit 1; }
g(){ git -C "$APP" "$@"; }
remote(){ ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=yes -o ClearAllForwardings=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=6 -n root@tracker-prod "$1"; }
cleanup(){
  rc=$?
  trap - EXIT
  if [[ "$PAUSED" == 1 ]]; then
    systemctl start tracker-upload-sync-dev.timer || echo "RELEASE_693_SYNC_TIMER_RESTART_FAILED" >&2
  fi
  [[ -z "$STAGE" ]] || rm -rf -- "$STAGE"
  echo "RELEASE_693_ROLLOUT_EXIT_STATUS=$rc"
  exit "$rc"
}
trap cleanup EXIT
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev &&
   -n "$(printenv INVOCATION_ID || true)" ]] ||
  fail "Detached root service on tracker-dev required"
[[ -x "$PY" ]] || fail "Tracker Python missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(g branch --show-current)" == main && -z "$(g status --porcelain)" ]] ||
  fail "Require clean DEV main"
systemctl is-active --quiet tracker || fail "DEV Tracker service inactive"
START="$(g rev-parse HEAD)"
[[ "$START" == "$BASE" || "$START" == "$TARGET" ]] ||
  fail "Unexpected DEV baseline $START"
g fetch origin main "refs/heads/$REF:refs/remotes/origin/$REF"
[[ "$(g rev-parse origin/main)" == "$BASE" || "$(g rev-parse origin/main)" == "$TARGET" ]] ||
  fail "Unexpected GitHub main commit"
[[ "$(g rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
  fail "Qualified Release 693 branch moved"
g merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Release ancestry verification failed"
EXPECTED="$(printf '%s\n' \
  app/routers/data_quality674.py app/routers/workouts654.py \
  app/templates/data_quality674.html app/templates/workouts654.html \
  scripts/tracker-preview693.sh scripts/tracker-release-scoped693.sh \
  scripts/tracker-workout-qr-retirement-review693.py \
  tests/test_integrated_productivity674.py tests/test_workout_no_camera692.py \
  tests/test_workout_no_qr693.py tests/test_workouts654.py tests/test_workouts656.py \
  | LC_ALL=C sort)"
[[ "$(g diff --name-only "$BASE" "$TARGET" | LC_ALL=C sort)" == "$EXPECTED" ]] ||
  fail "Source differs from approved 12-file manifest"
[[ -z "$(g diff --name-only "$BASE" "$TARGET" -- app/models.py app/migrations.py app/db.py app/workout_models654.py app/scoped_db390.py)" ]] ||
  fail "Unexpected schema changes"
g diff --check "$BASE" "$TARGET"
STAGE="$(mktemp -d /tmp/tracker-692-release.XXXXXXXX)"
chmod 700 "$STAGE"
g show "$TARGET:scripts/tracker-release.sh" > "$STAGE/runner.sh"
[[ "$(g hash-object "$STAGE/runner.sh")" == "$(g rev-parse "$TARGET:scripts/tracker-release.sh")" ]] ||
  fail "Staged signed runner blob mismatch"
bash -n "$STAGE/runner.sh"
echo "RELEASE_693_SOURCE_MANIFEST=VERIFIED"
echo "RELEASE_693_TEST_SCOPE=CHANGE_SCOPED_NO_FULL_SUITE"

if [[ "$START" == "$BASE" ]]; then
  if systemctl is-active --quiet tracker-upload-sync-dev.timer; then
    systemctl stop tracker-upload-sync-dev.timer
    PAUSED=1
    for ((i=0;i<120;i++)); do
      if ! systemctl is-active --quiet tracker-upload-sync-dev.service; then break; fi
      sleep 2
    done
    ! systemctl is-active --quiet tracker-upload-sync-dev.service ||
      fail "Upload synchronization still running"
    echo "RELEASE_693_DEV_UPLOAD_SYNC=PAUSED"
  fi
  echo "=== Guarded DEV release installation and focused tests ==="
  bash "$STAGE/runner.sh" --instance DEV --base "$BASE" --target "$TARGET" \
    --ref "$REF" 2>&1 | tee "$STAGE/dev.log"
  [[ "$(g rev-parse HEAD)" == "$TARGET" ]] || fail "DEV install commit mismatch"
fi

LOG=/etc/tracker-release/release-693-dev.log
[[ -f "$LOG" && ! -L "$LOG" ]] || fail "Missing DEV 693 receipt"
for marker in "DEV_QUALIFIED_COMMIT=$TARGET" \
  'RELEASE_SCOPED_PREFLIGHT=PASSED' 'FOCUSED_RELEASE_GATE=PASSED' \
  'DATABASE_BACKUP=SKIPPED_NO_MIGRATION' 'EXIT_STATUS=0'; do
  grep -Fxq "$marker" "$LOG" || fail "DEV receipt missing: $marker"
done
[[ "$(g rev-parse HEAD)" == "$TARGET" && -z "$(g status --porcelain)" ]] ||
  fail "DEV checkout not clean at qualified target"
systemctl is-active --quiet tracker || fail "DEV service inactive"
echo "RELEASE_693_DEV_QUALIFIED=VERIFIED"
if [[ "$PAUSED" == 1 ]]; then
  systemctl start tracker-upload-sync-dev.timer || fail "Upload sync restore failed"
  PAUSED=0
  echo "RELEASE_693_DEV_UPLOAD_SYNC=RESTORED"
fi

PROMOTER="$APP/scripts/tracker_promote568.py"
[[ -f "$PROMOTER" && ! -L "$PROMOTER" ]] || fail "DEV signer unavailable"
echo "=== Signed DEV-controlled PROD dry-run ==="
"$PY" "$PROMOTER" --release 693 --target "$TARGET" \
  --prod-base "$BASE" --ref "$REF" 2>&1 | tee "$STAGE/preflight.log"
grep -Fxq 'PREFLIGHT=PASSED' "$STAGE/preflight.log" ||
  fail "PROD preflight not verified"
grep -Fq 'DRY_RUN=PASSED' "$STAGE/preflight.log" ||
  fail "PROD dry run missing"
echo "RELEASE_693_PROD_PREFLIGHT=PASSED"

echo "=== Signed promotion and PROD installation from DEV ==="
"$PY" "$PROMOTER" --release 693 --target "$TARGET" \
  --prod-base "$BASE" --ref "$REF" --execute 2>&1 | tee "$STAGE/prod.log"
grep -Fxq 'DEV_CONTROLLED_RELEASE=SUCCESS' "$STAGE/prod.log" ||
  fail "Signed deployment not verified"
g fetch origin main
[[ "$(g rev-parse origin/main)" == "$TARGET" ]] ||
  fail "GitHub main promotion mismatch"
[[ "$(remote 'hostname -s')" == tracker-prod ]] ||
  fail "PROD host mismatch"
[[ "$(remote 'git -c safe.directory=/opt/tracker -C /opt/tracker rev-parse HEAD')" == "$TARGET" ]] ||
  fail "PROD installed SHA mismatch"
[[ "$(remote 'systemctl is-active tracker')" == active ]] ||
  fail "PROD service inactive"
remote 'grep -Fxq EXIT_STATUS=0 /etc/tracker-release/release-693-prod.log && grep -Fq "TRACKER RELEASE DEPLOYMENT SUCCESS" /etc/tracker-release/release-693-prod.log' ||
  fail "PROD receipt missing"
remote 'test ! -e /opt/tracker/app/static/js/tracker-workouts656.js && ! grep -q "Find a machine" /opt/tracker/app/templates/workouts654.html && ! grep -q "action=\"/workouts/qr\"" /opt/tracker/app/templates/workouts654.html && ! grep -q "name=\"qr_value\"" /opt/tracker/app/templates/workouts654.html && ! grep -q "@router.get(\"/workouts/qr\")" /opt/tracker/app/routers/workouts654.py && grep -q "Equipment &amp; Logging" /opt/tracker/app/templates/workouts654.html && grep -q "Machine Setup" /opt/tracker/app/templates/workouts654.html && grep -q "Find Machine" /opt/tracker/app/templates/workout_quick659.html && ! grep -q "Machine has no QR mapping" /opt/tracker/app/routers/data_quality674.py' ||
  fail "PROD installed QR cleanup source unverified"
echo "PROD_693_QR_MAPPING_UI=REMOVED_VERIFIED"
echo "PROD_DEPLOY_VERIFIED=$TARGET"
echo "RELEASE_693_DEV_INSTALLED=$TARGET"
echo "RELEASE_693_PROD_INSTALLED=$TARGET"
echo "DEV_CONTROLLED_RELEASE=SUCCESS"
echo "TRACKER_693_FULL_ROLLOUT=SUCCESS"
