#!/usr/bin/env bash
# Exact-commit, detached, DEV-controlled Tracker 690/691 to PROD rollout.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY=/opt/tracker/.venv/bin/python
OLD=ae8c75ef39ed26fa505be17e0d8b6152542cbf36
MID=6a8cd357e7e8925228d1a37c50572f93c4ec0943
NEW=869ada02eb9ac523ca9e8ce7c19ed6b92b303d68
PROD_BASE=b42b39cb9f490325358a9a7ddc305ac7ca6ed5fb
REF690=release/690-overview-card-density
REF691=release/691-coa-document-identifiers
PAUSED=0
TMP=
fail(){ echo "TRACKER_691_ROLLOUT_ERROR=$*" >&2; exit 1; }
g(){ git -C "$APP" "$@"; }
cleanup(){
  rc=$?
  trap - EXIT
  if [[ "$PAUSED" == 1 ]]; then systemctl start tracker-upload-sync-dev.timer || echo "UPLOAD_SYNC_RESTART_FAILED" >&2; fi
  if [[ -n "$TMP" ]]; then rm -rf -- "$TMP"; fi
  echo "TRACKER_691_ROLLOUT_EXIT_STATUS=$rc"
  exit "$rc"
}
trap cleanup EXIT
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev &&
   -n "$(printenv INVOCATION_ID || true)" ]] || fail "Requires detached root systemd service on tracker-dev"
[[ -x "$PY" ]] || fail "Tracker Python unavailable"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(g branch --show-current)" == main && -z "$(g status --porcelain)" ]] || fail "DEV not clean main"
systemctl is-active --quiet tracker || fail "DEV Tracker service inactive"
HEAD="$(g rev-parse HEAD)"
[[ "$HEAD" == "$OLD" || "$HEAD" == "$MID" || "$HEAD" == "$NEW" ]] || fail "Unexpected DEV commit $HEAD"
g fetch origin main "refs/heads/$REF690:refs/remotes/origin/$REF690" "refs/heads/$REF691:refs/remotes/origin/$REF691"
[[ "$(g rev-parse origin/main)" == "$PROD_BASE" || "$(g rev-parse origin/main)" == "$NEW" ]] || fail "Unexpected GitHub main"
[[ "$(g rev-parse "refs/remotes/origin/$REF690")" == "$MID" &&
   "$(g rev-parse "refs/remotes/origin/$REF691")" == "$NEW" ]] || fail "Qualified source ref moved"
g merge-base --is-ancestor "$OLD" "$MID" || fail "Release 690 ancestry invalid"
g merge-base --is-ancestor "$MID" "$NEW" || fail "Release 691 ancestry invalid"
[[ -z "$(g diff --name-only "$PROD_BASE" "$MID" -- app/models.py app/migrations.py)" ]] || fail "Unexpected schema changes before 691"
EXPECTED="$(printf '%s\n' app/migrations.py app/models.py app/routers/coas.py \
  app/static/css/tracker-coa-identifiers691.css app/templates/coa_edit.html \
  scripts/tracker-preview691.sh scripts/tracker-release-scoped691.sh scripts/tracker-release.sh \
  scripts/tracker_prod_remote568.sh scripts/tracker_schema_review691.py \
  tests/test_coa_csrf_surface691.py tests/test_coa_document_identifiers691.py \
  tests/test_coa_deploy_gate691.py | LC_ALL=C sort)"
[[ "$(g diff --name-only "$MID" "$NEW" | LC_ALL=C sort)" == "$EXPECTED" ]] || fail "Release 691 file manifest changed"
g diff --check "$PROD_BASE" "$NEW"
TMP="$(mktemp -d /tmp/tracker-full691.XXXXXXXX)"
stage(){
  g show "$1:$2" > "$3"
  [[ "$(g hash-object "$3")" == "$(g rev-parse "$1:$2")" ]] || fail "Git object hash mismatch: $2"
  bash -n "$3" || fail "Syntax error in signed source: $2"
}
stage "$MID" scripts/tracker-release.sh "$TMP/runner690.sh"
stage "$NEW" scripts/tracker-release.sh "$TMP/runner691.sh"
stage "$NEW" scripts/tracker-preview691.sh "$TMP/preview691.sh"
stage "$NEW" scripts/tracker_prod_remote568.sh "$TMP/remote691.sh"
echo "TRACKER_691_SOURCE_MANIFEST=VERIFIED"
echo "TRACKER_691_START_DEV=$HEAD"
echo "TRACKER_691_FULL_SUITE=NOT_REQUESTED"

if [[ "$HEAD" != "$NEW" ]]; then
  echo "=== Isolated requalification of corrected Release 691 ==="
  bash "$TMP/preview691.sh" 2>&1 | tee "$TMP/preview.log"
  grep -Fxq "RELEASE_691_PREVIEW_QUALIFIED=$NEW" "$TMP/preview.log" || fail "Preview target mismatch"
  grep -Fxq 'RELEASE_691_PREVIEW=PASSED_ISOLATED_NO_INSTALL' "$TMP/preview.log" || fail "Preview failed"
  grep -Fxq 'RELEASE_691_PREVIEW_EXIT_STATUS=0' "$TMP/preview.log" || fail "Preview exit unverified"
  echo "RELEASE_691_FINAL_PREVIEW=PASSED"
  if systemctl is-active --quiet tracker-upload-sync-dev.timer; then
    systemctl stop tracker-upload-sync-dev.timer
    PAUSED=1
    for ((i=0; i<120; i++)); do
      if ! systemctl is-active --quiet tracker-upload-sync-dev.service; then break; fi
      sleep 2
    done
    ! systemctl is-active --quiet tracker-upload-sync-dev.service || fail "Upload sync did not finish"
    echo "DEV_UPLOAD_SYNC_TIMER=PAUSED_FOR_DEPLOYMENT"
  fi
fi

if [[ "$(g rev-parse HEAD)" == "$OLD" ]]; then
  echo "=== Guarded DEV Release 690 ==="
  bash "$TMP/runner690.sh" --instance DEV --base "$OLD" --target "$MID" --ref "$REF690" 2>&1 | tee "$TMP/dev690.log"
  [[ "$(g rev-parse HEAD)" == "$MID" ]] || fail "DEV Release 690 installation mismatch"
  grep -Fxq "DEV_QUALIFIED_COMMIT=$MID" /etc/tracker-release/release-690-dev.log || fail "DEV 690 receipt missing"
  grep -Fxq 'EXIT_STATUS=0' /etc/tracker-release/release-690-dev.log || fail "DEV 690 receipt unsuccessful"
  echo "RELEASE_690_DEV_INSTALLED=$MID"
fi

if [[ "$(g rev-parse HEAD)" == "$MID" ]]; then
  echo "=== Guarded DEV Release 691 with verified migration backup ==="
  bash "$TMP/runner691.sh" --instance DEV --base "$MID" --target "$NEW" --ref "$REF691" --db-migration --reviewed-coa-691 2>&1 | tee "$TMP/dev691.log"
  [[ "$(g rev-parse HEAD)" == "$NEW" ]] || fail "DEV Release 691 installation mismatch"
  echo "RELEASE_691_DEV_INSTALLED=$NEW"
fi
DEV_LOG=/etc/tracker-release/release-691-dev.log
[[ "$(g rev-parse HEAD)" == "$NEW" && -z "$(g status --porcelain)" ]] || fail "DEV final source mismatch"
[[ -f "$DEV_LOG" && ! -L "$DEV_LOG" ]] || fail "Missing DEV 691 receipt"
for marker in "DEV_QUALIFIED_COMMIT=$NEW" 'COA_691_SCHEMA_PROCEDURE=AUTHORIZED' \
  'DATABASE_BACKUP=VERIFIED_FOR_MIGRATION' 'RELEASE_SCOPED_PREFLIGHT=PASSED' \
  'FOCUSED_RELEASE_GATE=PASSED' 'EXIT_STATUS=0'; do
  grep -Fxq "$marker" "$DEV_LOG" || fail "DEV 691 receipt missing: $marker"
done
systemctl is-active --quiet tracker || fail "DEV Tracker service inactive"
echo "RELEASE_691_DEV_QUALIFIED=VERIFIED"
if [[ "$PAUSED" == 1 ]]; then
  systemctl start tracker-upload-sync-dev.timer || fail "Could not restore upload sync timer"
  PAUSED=0
  echo "DEV_UPLOAD_SYNC_TIMER=RESTORED"
fi
PROMOTER="$APP/scripts/tracker_promote568.py"
[[ -f "$PROMOTER" && ! -L "$PROMOTER" ]] || fail "DEV signed promoter missing"
echo "=== Signed DEV-controlled PROD dry run ==="
"$PY" "$PROMOTER" --release 691 --target "$NEW" --prod-base "$PROD_BASE" --ref "$REF691" 2>&1 | tee "$TMP/preflight.log"
grep -Fxq 'PREFLIGHT=PASSED' "$TMP/preflight.log" || fail "PROD dry run not verified"
grep -Fq 'DRY_RUN=PASSED' "$TMP/preflight.log" || fail "PROD dry run unsuccessful"
echo "RELEASE_691_PROD_PREFLIGHT=PASSED"
echo "=== DEV-signed fast-forward PROD deployment ==="
"$PY" "$PROMOTER" --release 691 --target "$NEW" --prod-base "$PROD_BASE" --ref "$REF691" --execute 2>&1 | tee "$TMP/promote.log"
grep -Fxq 'DEV_CONTROLLED_RELEASE=SUCCESS' "$TMP/promote.log" || fail "PROD promotion incomplete"
g fetch origin main
[[ "$(g rev-parse origin/main)" == "$NEW" ]] || fail "GitHub main was not promoted"
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=yes -n)
[[ "$(ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -n root@tracker-prod 'hostname -s')" == tracker-prod ]] || fail "PROD host identity mismatch"
[[ "$(ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -n root@tracker-prod 'git -c safe.directory=/opt/tracker -C /opt/tracker rev-parse HEAD')" == "$NEW" ]] || fail "PROD installed commit mismatch"
[[ "$(ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -n root@tracker-prod 'systemctl is-active tracker')" == active ]] || fail "PROD service inactive"
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -n root@tracker-prod \
  'grep -Fxq DATABASE_BACKUP=VERIFIED_FOR_MIGRATION /etc/tracker-release/release-691-prod.log && grep -Fxq COA_691_PROD_FOCUSED_TESTS=PASSED /etc/tracker-release/release-691-prod.log && grep -Fxq EXIT_STATUS=0 /etc/tracker-release/release-691-prod.log' ||
  fail "PROD verified backup or scoped test receipt missing"
PROD_SCHEMA="$(ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -n root@tracker-prod \
  "/opt/tracker/.venv/bin/python -c 'import sqlite3; c=sqlite3.connect(\"file:/opt/tracker/data/tracker.db?mode=ro\", uri=True); print(int({\"job_id\",\"verify_code\"}.issubset({r[1] for r in c.execute(\"PRAGMA table_info(coa_attachments)\")})))'")"
[[ "$PROD_SCHEMA" == 1 ]] || fail "PROD COA attachment columns not present"
echo "PROD_691_COA_DOCUMENT_SCHEMA=VERIFIED"
echo "PROD_DEPLOY_VERIFIED=$NEW"
echo "RELEASE_691_DEV_INSTALLED=$NEW"
echo "RELEASE_691_PROD_INSTALLED=$NEW"
echo "DEV_CONTROLLED_RELEASE=SUCCESS"
echo "TRACKER_691_FULL_ROLLOUT=SUCCESS"
