#!/usr/bin/env bash
# Release 692: guarded detached DEV-only controlled PROD rollout.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY=/opt/tracker/.venv/bin/python
BASE=869ada02eb9ac523ca9e8ce7c19ed6b92b303d68
TARGET=696fe7f482436090df5342f76cd65b9fb5febad4
REF=release/692-remove-workout-qr-camera
STAGE=
PAUSED=0
fail(){ echo "RELEASE_692_ROLLOUT_ERROR=$*" >&2; exit 1; }
g(){ git -C "$APP" "$@"; }
remote(){ ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=yes -o ClearAllForwardings=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=6 -n root@tracker-prod "$1"; }
cleanup(){
  rc=$?
  trap - EXIT
  if [[ "$PAUSED" == 1 ]]; then
    systemctl start tracker-upload-sync-dev.timer || echo "RELEASE_692_SYNC_TIMER_RESTART_FAILED" >&2
  fi
  [[ -z "$STAGE" ]] || rm -rf -- "$STAGE"
  echo "RELEASE_692_ROLLOUT_EXIT_STATUS=$rc"
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
  fail "Qualified Release 692 branch moved"
g merge-base --is-ancestor "$BASE" "$TARGET" ||
  fail "Release ancestry verification failed"
EXPECTED="$(printf '%s\n' \
  app/routers/workouts656.py app/static/css/tracker-workouts656.css \
  app/static/js/tracker-workouts656.js app/templates/workout_progress656.html \
  app/templates/workouts654.html scripts/tracker-preview692.sh \
  scripts/tracker-release-scoped692.sh scripts/tracker-workout-camera-review692.py \
  scripts/tracker-workout-camera-test656.cjs tests/test_workout_no_camera692.py \
  tests/test_workouts656.py | LC_ALL=C sort)"
[[ "$(g diff --name-only "$BASE" "$TARGET" | LC_ALL=C sort)" == "$EXPECTED" ]] ||
  fail "Source differs from approved 11-file manifest"
[[ -z "$(g diff --name-only "$BASE" "$TARGET" -- app/models.py app/migrations.py app/db.py)" ]] ||
  fail "Unexpected schema changes"
g diff --check "$BASE" "$TARGET"
STAGE="$(mktemp -d /tmp/tracker-692-release.XXXXXXXX)"
chmod 700 "$STAGE"
g show "$TARGET:scripts/tracker-release.sh" > "$STAGE/runner.sh"
[[ "$(g hash-object "$STAGE/runner.sh")" == "$(g rev-parse "$TARGET:scripts/tracker-release.sh")" ]] ||
  fail "Staged signed runner blob mismatch"
bash -n "$STAGE/runner.sh"
echo "RELEASE_692_SOURCE_MANIFEST=VERIFIED"
echo "RELEASE_692_TEST_SCOPE=CHANGE_SCOPED_NO_FULL_SUITE"

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
    echo "RELEASE_692_DEV_UPLOAD_SYNC=PAUSED"
  fi
  echo "=== Guarded DEV release installation and focused tests ==="
  bash "$STAGE/runner.sh" --instance DEV --base "$BASE" --target "$TARGET" \
    --ref "$REF" 2>&1 | tee "$STAGE/dev.log"
  [[ "$(g rev-parse HEAD)" == "$TARGET" ]] || fail "DEV install commit mismatch"
fi

LOG=/etc/tracker-release/release-692-dev.log
[[ -f "$LOG" && ! -L "$LOG" ]] || fail "Missing DEV 692 receipt"
for marker in "DEV_QUALIFIED_COMMIT=$TARGET" \
  'RELEASE_SCOPED_PREFLIGHT=PASSED' 'FOCUSED_RELEASE_GATE=PASSED' \
  'DATABASE_BACKUP=SKIPPED_NO_MIGRATION' 'EXIT_STATUS=0'; do
  grep -Fxq "$marker" "$LOG" || fail "DEV receipt missing: $marker"
done
[[ "$(g rev-parse HEAD)" == "$TARGET" && -z "$(g status --porcelain)" ]] ||
  fail "DEV checkout not clean at qualified target"
systemctl is-active --quiet tracker || fail "DEV service inactive"
echo "RELEASE_692_DEV_QUALIFIED=VERIFIED"
if [[ "$PAUSED" == 1 ]]; then
  systemctl start tracker-upload-sync-dev.timer || fail "Upload sync restore failed"
  PAUSED=0
  echo "RELEASE_692_DEV_UPLOAD_SYNC=RESTORED"
fi

PROMOTER="$APP/scripts/tracker_promote568.py"
[[ -f "$PROMOTER" && ! -L "$PROMOTER" ]] || fail "DEV signer unavailable"
echo "=== Signed DEV-controlled PROD dry-run ==="
"$PY" "$PROMOTER" --release 692 --target "$TARGET" \
  --prod-base "$BASE" --ref "$REF" 2>&1 | tee "$STAGE/preflight.log"
grep -Fxq 'PREFLIGHT=PASSED' "$STAGE/preflight.log" ||
  fail "PROD preflight not verified"
grep -Fq 'DRY_RUN=PASSED' "$STAGE/preflight.log" ||
  fail "PROD dry run missing"
echo "RELEASE_692_PROD_PREFLIGHT=PASSED"

echo "=== Signed promotion and PROD installation from DEV ==="
"$PY" "$PROMOTER" --release 692 --target "$TARGET" \
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
remote 'grep -Fxq EXIT_STATUS=0 /etc/tracker-release/release-692-prod.log && grep -Fq "TRACKER RELEASE DEPLOYMENT SUCCESS" /etc/tracker-release/release-692-prod.log' ||
  fail "PROD receipt missing"
remote 'test ! -e /opt/tracker/app/static/js/tracker-workouts656.js && ! grep -q "workout-qr-camera656" /opt/tracker/app/templates/workouts654.html && grep -q "Equipment &amp; Logging" /opt/tracker/app/templates/workouts654.html' ||
  fail "PROD installed Workout scanner removal unverified"
echo "PROD_692_CAMERA_SCANNER=REMOVED_VERIFIED"
echo "PROD_DEPLOY_VERIFIED=$TARGET"
echo "RELEASE_692_DEV_INSTALLED=$TARGET"
echo "RELEASE_692_PROD_INSTALLED=$TARGET"
echo "DEV_CONTROLLED_RELEASE=SUCCESS"
echo "TRACKER_692_FULL_ROLLOUT=SUCCESS"
