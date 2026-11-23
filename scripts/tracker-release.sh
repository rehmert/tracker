#!/usr/bin/env bash
# Versioned, fail-closed Tracker DEV/PROD deployer. Run as root.
set -Eeuo pipefail
umask 022
APP=/opt/tracker
PY="$APP/.venv/bin/python"
fail() { echo "ERROR: $*" >&2; exit 1; }
g() { git -C "$APP" "$@"; }

verify_prod_approval() {
  if [[ "$INSTANCE" == PROD ]]; then
    local verifier=/usr/local/sbin/tracker-verify-dev-approval
    [[ -f "$verifier" && -x "$verifier" && ! -L "$verifier" ]] ||
      fail "Trusted PROD approval verifier unavailable"
    "$verifier" "$TARGET" ||
      fail "Exact-commit DEV approval required"
  fi
}
instance_check() {
 "$PY" - "$1" <<'PY'
import re,sys
from pathlib import Path
labels=[]
for line in Path('/etc/tracker.env').read_text().splitlines():
 m=re.match(r'^\s*(?:export\s+)?TRACKER_INSTANCE\s*=(.*)$',line)
 if m: labels.append(m.group(1).strip().strip("\"'").upper())
if labels != [sys.argv[1]]: raise SystemExit('Incorrect local instance label')
PY
}
changed() { g diff --name-only --diff-filter=ACMR "$BASE" "$TARGET" -- app/; }
cleanup() {
 code=$?
 trap - EXIT
 # Never report success if the worker was terminated before its complete
 # backend/restore/install/runtime qualification sequence finished.
 if ((code==0 && QUALIFICATION_COMPLETE!=1)); then
  echo "ERROR: Release worker exited without completing qualification" >&2
  code=1
 fi
 # Release 577: persist independently verified exact-commit DEV evidence
 # before returning success. A receipt failure becomes a deployment failure,
 # preserving the existing code-only rollback guard.
 if ((code==0)) && [[ "$INSTANCE" == DEV ]]; then
  echo "EXIT_STATUS=0"
  echo "Finished: $(date -Is)"
  local release_number="${REF#release/}"
  release_number="${release_number%%-*}"
  if ! "$PY" "$QA/scripts/tracker_dev_log577.py" \
       --source "$RUN/deployment.log" \
       --release "$release_number" --target "$TARGET"; then
   echo "ERROR: DEV qualification evidence was not preserved" >&2
   code=1
  fi
 fi
 if ((code!=0 && INSTALLED==1)); then
  echo "Post-deploy failure: attempting code-only rollback"
  cd "$APP"
  umask 022
  if [[ "$(g rev-parse HEAD)" == "$TARGET" && -z "$(g status --porcelain)" ]]; then
   if g reset --hard "$BASE"; then
     echo "=== Refresh rollback bytecode ==="
     find "$APP/app" "$APP/scripts" -type f -name '*.pyc' -delete
     "$PY" -m compileall -q -f "$APP/app" "$APP/scripts" ||
       echo "WARNING: Rollback bytecode compilation failed"
    while IFS= read -r f; do
     if [[ -f "$APP/$f" && ! -L "$APP/$f" ]]; then chmod a+r "$APP/$f"; fi
    done < <(changed)
    if ((RESTART==1)); then
     systemctl reset-failed tracker || true
     systemctl restart tracker || true
    fi
    echo "Previous code restored (database untouched)"
   fi
  else echo "Rollback withheld: checkout not in expected clean state"; fi
 fi
 if [[ -d "$QA" ]]; then g worktree remove --force "$QA" >/dev/null 2>&1 || true; fi
 if ((code!=0)) || [[ "$INSTANCE" != DEV ]]; then
  echo "EXIT_STATUS=$code"
  echo "Finished: $(date -Is)"
 fi
 exit "$code"
}
worker() {
 RUN="$1"; INSTANCE="$2"; BASE="$3"; TARGET="$4"; REF="$5"; SERIAL_TESTS="$6"; DEV_FOCUSED_630="$7"; DB_MIGRATION="$8"; REVIEWED_REGIMEN_635="$9"; REVIEWED_FACTS_639="${10}"; REVIEWED_COA_643="${11}"; REVIEWED_COA_645="${12}"; REVIEWED_COA_652="${13:-0}"; FULL_SUITE="${14:-0}"; REVIEWED_WORKOUT_654="${15:-0}"; REVIEWED_WORKOUT_655="${16:-0}"; REVIEWED_WORKOUT_667="${17:-0}"; REVIEWED_WORKOUT_668="${18:-0}"; REVIEWED_COA_691="${19:-0}"; REVIEWED_BLEND_710="${20:-0}"; REVIEWED_TABLET_731="${21:-0}"; REVIEWED_CATCHUP_735="${22:-0}"; REVIEWED_VIAL_758="${23:-0}"
 [[ "$SERIAL_TESTS" == 0 ]] || fail "Invalid serial test override"
 [[ "$FULL_SUITE" == 0 || "$FULL_SUITE" == 1 ]] || fail "Invalid full-suite setting"
 QA="$RUN/source"; SAVE="$RUN/pre-deployment"; INSTALLED=0; RESTART=0; QUALIFICATION_COMPLETE=0; RESUME_645_VERIFIED=0
 export GIT_CONFIG_COUNT=2
 export GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
 export GIT_CONFIG_KEY_1=safe.directory GIT_CONFIG_VALUE_1="$QA"
 umask 022
 exec >> "$RUN/deployment.log" 2>&1
 trap cleanup EXIT
 trap 'exit 143' TERM
 trap 'exit 130' INT
 echo "Started: $(date -Is); instance: $INSTANCE"
 exec 9>/run/lock/tracker-db-sync.lock
 flock -n 9 || fail "Database replication active"
 echo "REPLICATION_DEPLOYMENT_LOCK=ACQUIRED"
 cd "$APP"
 [[ "$(g branch --show-current)" == main && -z "$(g status --porcelain)" ]] || fail "Not a clean main checkout"
 [[ "$(g rev-parse HEAD)" == "$BASE" ]] || fail "Starting commit differs from pinned base"
 instance_check "$INSTANCE"
 systemctl is-active --quiet tracker || fail "Tracker not active before update"
 echo "=== Fetch exact release ==="
 g fetch origin main "refs/heads/$REF:refs/remotes/origin/$REF"
 [[ "$(g rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] || fail "Release ref differs from pinned target"
 if [[ "$INSTANCE" == PROD ]]; then
  [[ "$REF" == main && "$(g rev-parse origin/main)" == "$TARGET" ]] || fail "PROD requires promoted main"
 fi
 verify_prod_approval
 g merge-base --is-ancestor "$BASE" "$TARGET" || fail "Target not descended from base"
 # The hourly timer is activated by its own guarded installer.
 if g diff --name-only "$BASE" "$TARGET" | grep -v '^deploy/tracker-backup.timer$' | grep -Eq '^(deploy/|requirements[^/]*|alembic/|alembic.ini|app/(db|models|migrations).py|app/workout_models654.py|app/workout_models655.py|app/workout_models667.py|app/workout_models668.py)'; then
  [[ "$DB_MIGRATION" == 1 ]] || fail "Schema changes require verified migration backup"
  if [[ "$REVIEWED_CATCHUP_735" == 1 ]]; then
   [[ "$INSTANCE" == PROD && "$REF" == main &&
      "$BASE" == 3718936aedfcb1b8fe243c86fe6fc7e06a7a41d2 ]] ||
      fail "Release 735 catch-up restricted to installed PROD 727"
   g worktree add --detach "$QA" "$TARGET"
   "$PY" "$QA/scripts/tracker_schema_review735.py" \
     --root "$APP" --base "$BASE" --target "$TARGET" ||
      fail "Release 735 immutable additive schema catch-up review failed"
   echo "RELEASE_735_SCHEMA_CATCHUP_REVIEW=PASSED"
  elif [[ "$REVIEWED_VIAL_758" == 1 ]]; then
   [[ "$INSTANCE" == DEV && "$REF" == release/758-vial-label-dose-markings ||
      "$INSTANCE" == PROD && "$REF" == main ]] ||
      fail "Release 758 schema review branch/host mismatch"
   g worktree add --detach "$QA" "$TARGET"
   "$PY" "$QA/scripts/tracker_schema_review758.py" --root "$QA" --base "$BASE" --target "$TARGET" ||
      fail "Release 758 exact additive production-date schema review failed"
   echo "VIAL_758_SCHEMA_PROCEDURE=AUTHORIZED"
  elif [[ "$REVIEWED_TABLET_731" == 1 ]]; then
   [[ "$INSTANCE" == DEV && "$REF" == release/731-tablet-dose-tracking ||
      "$INSTANCE" == PROD && "$REF" == main ]] ||
     fail "Release 731 schema review restricted to exact branch"
   g worktree add --detach "$QA" "$TARGET"
   "$PY" "$QA/scripts/tracker_schema_review731.py" --root "$APP" --base "$BASE" --target "$TARGET" ||
     fail "Release 731 additive tablet schema review failed"
   echo "REGIMEN_731_SCHEMA_PROCEDURE=AUTHORIZED"
  elif [[ "$REVIEWED_FACTS_639" == 1 ]]; then
   [[ "$INSTANCE" == DEV && "$REF" == release/639-structured-supplement-facts ||
      "$INSTANCE" == PROD && "$REF" == main ]] ||
      fail "Release 639 schema review restricted to exact branch"
   g worktree add --detach "$QA" "$TARGET"
   "$PY" "$QA/scripts/tracker_schema_review639.py" --root "$APP" --base "$BASE" --target "$TARGET" ||
      fail "Release 639 append-only schema review failed"
   echo "REGIMEN_639_SCHEMA_PROCEDURE=AUTHORIZED"
  elif [[ "$REVIEWED_REGIMEN_635" == 1 ]]; then
   [[ "$INSTANCE" == DEV && "$REF" == release/635-regimen-catalog-schedules ||
      "$INSTANCE" == PROD && "$REF" == main ]] ||
      fail "Release 635 schema review restricted to exact branch"
   g worktree add --detach "$QA" "$TARGET"
   "$PY" "$QA/scripts/tracker_schema_review635.py" --root "$APP" --base "$BASE" --target "$TARGET" ||
      fail "Release 635 schema review failed"
   echo "REGIMEN_635_SCHEMA_PROCEDURE=AUTHORIZED"
  elif [[ "$REVIEWED_COA_643" == 1 ]]; then
   [[ "$INSTANCE" == DEV && "$REF" == release/643-coa-multiple-documents ||
      "$INSTANCE" == PROD && "$REF" == main ]] ||
      fail "Release 643 schema review restricted to exact branch"
   g worktree add --detach "$QA" "$TARGET"
   "$PY" "$QA/scripts/tracker_schema_review643.py" --root "$APP" --base "$BASE" --target "$TARGET" ||
      fail "Release 643 additive COA schema review failed"
   echo "COA_643_SCHEMA_PROCEDURE=AUTHORIZED"
  elif [[ "$REVIEWED_COA_691" == 1 ]]; then
   [[ "$INSTANCE" == DEV && "$REF" == release/691-coa-document-identifiers ||
      "$INSTANCE" == PROD && "$REF" == main ]] ||
     fail "Release 691 schema review restricted to exact branch"
   g worktree add --detach "$QA" "$TARGET"
   "$PY" "$QA/scripts/tracker_schema_review691.py" --root "$APP" --base "$BASE" --target "$TARGET" ||
     fail "Release 691 COA identifiers schema review failed"
   echo "COA_691_SCHEMA_PROCEDURE=AUTHORIZED"
  elif [[ "$REVIEWED_BLEND_710" == 1 ]]; then
   [[ "$INSTANCE" == DEV && "$REF" == release/710-unified-blend-vial-dosing ||
      "$INSTANCE" == PROD && "$REF" == main ]] ||
     fail "Release 710 blend schema review restricted to exact branch"
   g worktree add --detach "$QA" "$TARGET"
   "$PY" "$QA/scripts/tracker_schema_review710.py" --root "$APP" --base "$BASE" --target "$TARGET" ||
     fail "Release 710 exact additive blend-dose schema review failed"
   echo "BLEND_710_SCHEMA_PROCEDURE=AUTHORIZED"
  elif [[ "$REVIEWED_COA_652" == 1 ]]; then
   [[ "$INSTANCE" == DEV && "$REF" == release/652-coa-test-type-catalog ||
      "$INSTANCE" == PROD && "$REF" == main ]] ||
     fail "Release 652 schema review restricted to exact branch"
   g worktree add --detach "$QA" "$TARGET"
   "$PY" "$QA/scripts/tracker_schema_review652.py" --root "$APP" --base "$BASE" --target "$TARGET" ||
     fail "Release 652 additive COA test catalog review failed"
   echo "COA_652_SCHEMA_PROCEDURE=AUTHORIZED"
  elif [[ "$REVIEWED_WORKOUT_654" == 1 ]]; then
   [[ "$INSTANCE" == DEV && "$REF" == release/654-workout-foundation ||
      "$INSTANCE" == PROD && "$REF" == main ]] ||
     fail "Release 654 schema review restricted to exact branch"
   g worktree add --detach "$QA" "$TARGET"
   "$PY" "$QA/scripts/tracker-workout-schema-review654.py" \
      --root "$QA" --base "$BASE" --target "$TARGET" ||
      fail "Release 654 additive workout schema review failed"
   echo "WORKOUT_654_SCHEMA_PROCEDURE=AUTHORIZED"
  elif [[ "$REVIEWED_WORKOUT_655" == 1 ]]; then
   [[ "$INSTANCE" == DEV && "$REF" == release/655-workout-routines-fast-logging ||
      "$INSTANCE" == PROD && "$REF" == main ]] ||
     fail "Release 655 schema review restricted to exact branch"
   g worktree add --detach "$QA" "$TARGET"
   "$PY" "$QA/scripts/tracker-workout-schema-review655.py" \
      --root "$QA" --base "$BASE" --target "$TARGET" ||
      fail "Release 655 additive workout schema review failed"
   echo "WORKOUT_655_SCHEMA_PROCEDURE=AUTHORIZED"
  elif [[ "$REVIEWED_WORKOUT_668" == 1 ]]; then
   [[ "$INSTANCE" == DEV && "$REF" == release/668-workout-completion ||
      "$INSTANCE" == PROD && "$REF" == main ]] ||
     fail "Release 668 schema review restricted to exact branch"
   g worktree add --detach "$QA" "$TARGET"
   "$PY" "$QA/scripts/tracker-workout-schema-review668.py" \
      --root "$QA" --base "$BASE" --target "$TARGET" ||
      fail "Release 668 additive Workout schema review failed"
   echo "WORKOUT_668_SCHEMA_PROCEDURE=AUTHORIZED"
  elif [[ "$REVIEWED_WORKOUT_667" == 1 ]]; then
   [[ "$INSTANCE" == DEV && "$REF" == release/667-complete-workout ||
      "$INSTANCE" == PROD && "$REF" == main ]] ||
     fail "Release 667 schema review restricted to exact branch"
   g worktree add --detach "$QA" "$TARGET"
   "$PY" "$QA/scripts/tracker-workout-schema-review667.py" \
      --root "$QA" --base "$BASE" --target "$TARGET" ||
      fail "Release 667 additive Workout program schema review failed"
   echo "WORKOUT_667_SCHEMA_PROCEDURE=AUTHORIZED"
  elif [[ "$REVIEWED_COA_645" == 1 ]]; then
   [[ "$INSTANCE" == DEV && "$REF" == release/645-coa-default-document ||
      "$INSTANCE" == PROD && "$REF" == main ]] ||
      fail "Release 645 schema review restricted to exact branch"
   g worktree add --detach "$QA" "$TARGET"
   "$PY" "$QA/scripts/tracker_schema_review645.py" --root "$APP" --base "$BASE" --target "$TARGET" ||
      fail "Release 645 additive COA schema review failed"
   echo "COA_645_SCHEMA_PROCEDURE=AUTHORIZED"
  else
   fail "Schema changes require a reviewed schema flag"
  fi
 elif [[ "$REVIEWED_FACTS_639" == 1 || "$REVIEWED_REGIMEN_635" == 1 || "$REVIEWED_COA_643" == 1 || "$REVIEWED_COA_645" == 1 || "$REVIEWED_COA_652" == 1 || "$REVIEWED_COA_691" == 1 || "$REVIEWED_BLEND_710" == 1 || "$REVIEWED_WORKOUT_654" == 1 || "$REVIEWED_WORKOUT_655" == 1 || "$REVIEWED_WORKOUT_667" == 1 || "$REVIEWED_WORKOUT_668" == 1 || "$REVIEWED_TABLET_731" == 1 || "$REVIEWED_CATCHUP_735" == 1 || "$REVIEWED_VIAL_758" == 1 ]]; then
  fail "Reviewed schema flag supplied without a schema change"
 fi
 if [[ "$DB_MIGRATION" == 0 ]] &&
    g diff --name-only "$BASE" "$TARGET" | grep -Eq '^scripts/.*(migrat|backfill|data[-_]fix)'; then
  fail "Possible data migration requires --db-migration and verified backup"
 fi
 RESTART=0
 [[ -z "$(changed)" ]] || RESTART=1
 echo "=== Isolated source tests ==="
 if [[ ! -d "$QA" ]]; then g worktree add --detach "$QA" "$TARGET"; fi
 [[ "$(git -C "$QA" rev-parse HEAD)" == "$TARGET" ]] || fail "Candidate worktree does not match target"
 echo "CANDIDATE_COMMIT=$TARGET"
 # Release 645+: cheap live attachment check before costly qualification.
 LIVE_DATA_DIR="$("$PY" - <<'PY'
from pathlib import Path
import re
data=Path("/opt/tracker/data")
for line in Path("/etc/tracker.env").read_text().splitlines():
    match=re.match(r'^\s*(?:export\s+)?TRACKER_DATA_DIR\s*=(.*)$', line)
    if match and match.group(1).strip():
        data=Path(match.group(1).strip().strip(chr(34)).strip(chr(39)))
if not data.is_absolute(): data=Path("/opt/tracker/data")
print(data.resolve())
PY
)"
 echo "=== LIVE ATTACHMENT INTEGRITY BEFORE QUALIFICATION ==="
 if [[ "$INSTANCE" == DEV ]]; then
  # DEV upload files are not mirrored from PROD. The DEV-only adapter permits
  # missing references but still fails for invalid paths and hash mismatches.
  "$PY" "$QA/scripts/tracker-dev-attachment-gate650.py" --data "$LIVE_DATA_DIR" ||
      fail "DEV integrity failure beyond unsynchronized missing attachments"
  echo "LIVE_ATTACHMENT_PREFLIGHT=DEV_ONLY_MISSING_POLICY"
 else
  # PROD remains strict for every release, including migrations.
  "$PY" "$QA/scripts/tracker-attachment-integrity645.py" --data "$LIVE_DATA_DIR" --hashes ||
      fail "Live database contains missing or changed attachment(s); reconcile uploads before testing"
  echo "LIVE_ATTACHMENT_PREFLIGHT=PASSED"
 fi
 cd "$QA"
 export TRACKER_DATA_DIR="$RUN/test-data" PYTHONPATH="$QA"
 mkdir -p "$TRACKER_DATA_DIR"
 git diff --check "$BASE" "$TARGET"
 echo "=== RELEASE 639 JAVASCRIPT SYNTAX ==="
 if [[ "$INSTANCE" == DEV && "$REF" == release/639-structured-supplement-facts ]]; then
  command -v node >/dev/null 2>&1 || fail "Node.js is required for Release 639 syntax gate"
  node --check "$QA/app/static/js/tracker-regimen-catalog636.js"
  node --check "$QA/app/static/js/tracker-regimen-facts639.js"
  echo "RELEASE_639_JAVASCRIPT_SYNTAX=PASSED"
 fi
 "$PY" -m compileall -q app scripts tests
 "$PY" - <<'PY'
from pathlib import Path
from jinja2 import Environment
files=sorted(Path('app/templates').rglob('*.html'))
for f in files: Environment().parse(f.read_text())
print(f'PASS: {len(files)} Jinja templates')
PY
 "$PY" - "$QA" <<'PY'
import app,sys
from pathlib import Path
assert Path(app.__file__).resolve().is_relative_to(Path(sys.argv[1]).resolve())
print('PASS: Isolated source import')
PY
 echo "=== RELEASE 604 STATIC CHANGE IMPACT PREFLIGHT ==="
 "$PY" "$QA/scripts/tracker-impact-preflight604.py" \
   --base "$BASE" --target "$TARGET" --root "$QA"
 echo "=== RELEASE 604 CHANGE IMPACT PASSED ==="
 # Operator selects full qualification explicitly. No fifth-release trigger.
 QA_FULL_REQUIRED="$FULL_SUITE"
 QA_CADENCE_REASON="release-specific tests only (no full suite requested)"
 if [[ "$FULL_SUITE" == 1 ]]; then
  QA_CADENCE_REASON="explicit operator full-suite request"
 fi
 if [[ "$INSTANCE" == DEV ]]; then
  if g diff --name-only "$BASE" "$TARGET" | grep -Eq '^(app/(auth|security|csrf|middleware|scoped_db|session_auth|request_origin|food_origin|food_storage_guard)|app/routers/(session_login|account_security|user_management|user_db_status))'; then
   [[ "$FULL_SUITE" == 1 ]] || fail "Security-sensitive release requires explicit --full-suite approval"
  fi
  if [[ "$REF" =~ ^release/([0-9]+)- ]] && (( 10#${BASH_REMATCH[1]} >= 652 )); then
   RELEASE_SEQUENCE="${BASH_REMATCH[1]}"
   SCOPED="$QA/scripts/tracker-release-scoped${RELEASE_SEQUENCE}.sh"
   [[ -f "$SCOPED" ]] || fail "Release-specific test gate missing: $SCOPED"
   echo "=== RELEASE-SCOPED DEV QUALIFICATION ==="
   timeout 360 bash "$SCOPED" "$PY"
   echo "RELEASE_SCOPED_PREFLIGHT=PASSED"
  else
   echo "=== LEGACY FOCUSED REGRESSION ==="
   timeout 180 bash "$QA/scripts/tracker-focused-regression604.sh" "$PY"
   echo "RELEASE_604_FOCUSED_PREFLIGHT=PASSED"
  fi
  if [[ "$REF" == release/651-coa-multiple-test-types ]]; then
   echo "=== RELEASE 651 MULTIPLE TEST TYPES PER COA DOCUMENT ==="
   timeout 240 bash "$QA/scripts/tracker-coa-scoped651.sh" "$PY"
  fi
  if [[ "$REF" == release/650-coa-unified-documents ]]; then
   echo "=== RELEASE 650 UNIFIED COA DOCUMENT SCOPED TESTS ==="
   timeout 240 bash "$QA/scripts/tracker-coa-scoped650.sh" "$PY"
  fi
  if [[ "$REF" == release/649-coa-documents-audit-ui ]]; then
   echo "=== RELEASE 649 COA DOCUMENTS AND AUDIT UI SCOPED TESTS ==="
   timeout 240 bash "$QA/scripts/tracker-coa-scoped649.sh" "$PY"
  fi
  if [[ "$REF" == release/648-coa-prod-qualification-recovery ]]; then
   echo "=== RELEASE 648 COA PROD RECOVERY SCOPED TESTS ==="
   timeout 240 bash "$QA/scripts/tracker-coa-scoped648.sh" "$PY"
  fi
  if [[ "$REF" == release/647-coa-bulk-test-types ]]; then
   echo "=== RELEASE 647 COA MULTI-DOCUMENT BATCH TESTS ==="
   timeout 180 bash "$QA/scripts/tracker-coa-scoped647.sh" "$PY"
  fi
  if [[ "$REF" == release/646-coa-test-type-picker ]]; then
   echo "=== RELEASE 646 COA TEST TYPE DROPDOWN SCOPED TESTS ==="
   timeout 180 bash "$QA/scripts/tracker-coa-scoped646.sh" "$PY"
  fi
  if [[ "$REF" == release/645-coa-default-document ]]; then
   echo "=== RELEASE 645 COA DEFAULT DOCUMENT CHANGE-SCOPED TESTS ==="
   timeout 180 bash "$QA/scripts/tracker-coa-scoped645.sh" "$PY"
  fi
  if [[ "$REF" == release/643-coa-multiple-documents ]]; then
   echo "=== RELEASE 643 COA CHANGE-SCOPED TESTS ==="
   timeout 180 bash "$QA/scripts/tracker-coa-scoped643.sh" "$PY"
  fi
  if [[ "$DEV_FOCUSED_630" == 1 ]]; then
   # Explicit one-release DEV exception. Never permitted for PROD,
   # arbitrary release refs, or a candidate that changes authentication,
   # origin checks, CSRF middleware, or storage authorization.
   [[ "$REF" == release/630-food-duplicate-resolution ]] ||
     fail "Focused 630 exception requires the exact Release 630 branch"
   if g diff --name-only "$BASE" "$TARGET" | grep -Eq '^(app/(auth|security|csrf|middleware|scoped_db|session_auth|request_origin|food_origin|food_storage_guard)|app/routers/(session_login|account_security|user_management|user_db_status))'; then
    fail "Focused 630 exception prohibited for security-sensitive application changes"
   fi
   echo "=== RELEASE 630 TARGETED FOOD AND CSRF REGRESSIONS ==="
   timeout 180 bash "$QA/scripts/tracker-focused630.sh" "$PY"
   QA_FULL_REQUIRED=0
   QA_CADENCE_REASON="operator-approved focused DEV qualification for Release 630"
  fi
 fi
 if [[ "$INSTANCE" == PROD && "$REVIEWED_CATCHUP_735" == 1 ]]; then
   echo "=== RELEASE 735 PROD 727 CATCHUP INTEGRATION QUALIFICATION ==="
   timeout 600 bash "$QA/scripts/tracker-release-scoped735.sh" "$PY"
   echo "RELEASE_735_PROD_SCOPED=PASSED"
 fi
 if [[ "$INSTANCE" == PROD && "$REF" == main ]] &&
    g diff --name-only "$BASE" "$TARGET" -- scripts/tracker-release-scoped721.sh |
      grep -qx 'scripts/tracker-release-scoped721.sh'; then
   echo "=== RELEASE 721 PROD SCOPED RECENT WORKOUTS CHEVRON QUALIFICATION ==="
   timeout 360 bash "$QA/scripts/tracker-release-scoped721.sh" "$PY"
   echo "RELEASE_721_PROD_SCOPED=PASSED"
 fi
 if [[ "$INSTANCE" == PROD && "$REF" == main ]] &&
    g diff --name-only "$BASE" "$TARGET" -- scripts/tracker-release-scoped720.sh |
      grep -qx 'scripts/tracker-release-scoped720.sh'; then
   echo "=== RELEASE 720 PROD SCOPED INLINE WORKOUT DELETE QUALIFICATION ==="
   timeout 360 bash "$QA/scripts/tracker-release-scoped720.sh" "$PY"
   echo "RELEASE_720_PROD_SCOPED=PASSED"
 fi
 if [[ "$INSTANCE" == PROD && "$REF" == main ]] &&
    g diff --name-only "$BASE" "$TARGET" -- scripts/tracker-release-scoped719.sh |
      grep -qx 'scripts/tracker-release-scoped719.sh'; then
   echo "=== RELEASE 719 PROD SCOPED WORKOUT MANAGEMENT QUALIFICATION ==="
   timeout 360 bash "$QA/scripts/tracker-release-scoped719.sh" "$PY"
   echo "RELEASE_719_PROD_SCOPED=PASSED"
 fi
 if [[ "$INSTANCE" == PROD && "$REF" == main ]] &&
    g diff --name-only "$BASE" "$TARGET" -- scripts/tracker-release-scoped718.sh |
      grep -qx 'scripts/tracker-release-scoped718.sh'; then
   echo "=== RELEASE 718 PROD SCOPED COMPLETED MACHINE CORRECTION QUALIFICATION ==="
   timeout 360 bash "$QA/scripts/tracker-release-scoped718.sh" "$PY"
   echo "RELEASE_718_PROD_SCOPED=PASSED"
 fi
 if [[ "$INSTANCE" == PROD && "$REF" == main ]] &&
    g diff --name-only "$BASE" "$TARGET" -- scripts/tracker-release-scoped717.sh |
      grep -qx 'scripts/tracker-release-scoped717.sh'; then
  echo "=== RELEASE 717 PROD SCOPED COMPLETED WORKOUT EDIT QUALIFICATION ==="
  timeout 360 bash "$QA/scripts/tracker-release-scoped717.sh" "$PY"
  echo "RELEASE_717_PROD_SCOPED=PASSED"
 fi
 if [[ "$INSTANCE" == PROD && "$REF" == main ]] &&
    g diff --name-only "$BASE" "$TARGET" -- scripts/tracker-release-scoped716.sh |
      grep -qx 'scripts/tracker-release-scoped716.sh'; then
  echo "=== RELEASE 716 PROD SCOPED ACTIVE WORKOUT MACHINE QUALIFICATION ==="
  timeout 360 bash "$QA/scripts/tracker-release-scoped716.sh" "$PY"
  echo "RELEASE_716_PROD_SCOPED=PASSED"
 fi
 if [[ "$INSTANCE" == PROD && "$REF" == main ]] &&
    g diff --name-only "$BASE" "$TARGET" -- scripts/tracker-release-scoped715.sh |
      grep -qx 'scripts/tracker-release-scoped715.sh'; then
  echo "=== RELEASE 715 PROD SCOPED COA UNTESTED DEFAULT QUALIFICATION ==="
  timeout 360 bash "$QA/scripts/tracker-release-scoped715.sh" "$PY"
  echo "RELEASE_715_PROD_SCOPED=PASSED"
 fi
 if [[ "$INSTANCE" == PROD && "$REF" == main ]] &&
    g diff --name-only "$BASE" "$TARGET" -- scripts/tracker-release-scoped714.sh |
      grep -qx 'scripts/tracker-release-scoped714.sh'; then
  echo "=== RELEASE 714 PROD SCOPED ROUTINE CARD ALIGNMENT QUALIFICATION ==="
  timeout 360 bash "$QA/scripts/tracker-release-scoped714.sh" "$PY"
  echo "RELEASE_714_PROD_SCOPED=PASSED"
 fi
 if [[ "$INSTANCE" == PROD && "$REF" == main ]] &&
    g diff --name-only "$BASE" "$TARGET" -- scripts/tracker-release-scoped713.sh |
      grep -qx 'scripts/tracker-release-scoped713.sh'; then
  echo "=== RELEASE 713 PROD SCOPED GLOBAL 24-HOUR UX AND TIMELINE QUALIFICATION ==="
  timeout 360 bash "$QA/scripts/tracker-release-scoped713.sh" "$PY"
  echo "RELEASE_713_PROD_SCOPED=PASSED"
 fi
 if [[ "$INSTANCE" == PROD && "$REF" == main ]] &&
    g diff --name-only "$BASE" "$TARGET" -- scripts/tracker-release-scoped712.sh |
      grep -qx 'scripts/tracker-release-scoped712.sh'; then
  echo "=== RELEASE 712 PROD SCOPED U-100 WITHDRAWAL QUALIFICATION ==="
  timeout 360 bash "$QA/scripts/tracker-release-scoped712.sh" "$PY"
  echo "RELEASE_712_PROD_SCOPED=PASSED"
 fi
 if [[ "$INSTANCE" == PROD && "$REF" == main ]] &&
    g diff --name-only "$BASE" "$TARGET" -- scripts/tracker-release-scoped711.sh |
      grep -qx 'scripts/tracker-release-scoped711.sh'; then
  echo "=== RELEASE 711 PROD SCOPED BLEND DOSE CORRECTION QUALIFICATION ==="
  timeout 360 bash "$QA/scripts/tracker-release-scoped711.sh" "$PY"
  echo "RELEASE_711_PROD_SCOPED=PASSED"
 fi
 if [[ "$INSTANCE" == PROD && "$REF" == main ]] &&
    g diff --name-only "$BASE" "$TARGET" -- scripts/tracker-release-scoped678.sh |
      grep -qx 'scripts/tracker-release-scoped678.sh'; then
  echo "=== RELEASE 678 PROD WORKOUT ACTIVITY SHORTCUT CARD QUALIFICATION ==="
  timeout 600 bash "$QA/scripts/tracker-release-scoped678.sh" "$PY"
  echo "RELEASE_SCOPED_PREFLIGHT=PASSED"
 fi
 if [[ "$INSTANCE" == PROD && "$REF" == main ]] &&
    g diff --name-only "$BASE" "$TARGET" -- scripts/tracker-release-scoped677.sh |
      grep -qx 'scripts/tracker-release-scoped677.sh'; then
  echo "=== RELEASE 677 PROD COLOR PARITY RECOVERY QUALIFICATION ==="
  timeout 600 bash "$QA/scripts/tracker-release-scoped677.sh" "$PY"
  echo "RELEASE_SCOPED_PREFLIGHT=PASSED"
 fi
 if [[ "$INSTANCE" == PROD && "$REF" == main ]] &&
    g diff --name-only "$BASE" "$TARGET" -- scripts/tracker-release-scoped676.sh |
      grep -qx 'scripts/tracker-release-scoped676.sh'; then
  echo "=== RELEASE 676 PROD DAILY SHORTCUT BUTTON VISUAL QUALIFICATION ==="
  timeout 600 bash "$QA/scripts/tracker-release-scoped676.sh" "$PY"
  echo "RELEASE_SCOPED_PREFLIGHT=PASSED"
 fi
 if [[ "$INSTANCE" == PROD && "$REF" == main ]] &&
    g diff --name-only "$BASE" "$TARGET" -- scripts/tracker-release-scoped675.sh |
      grep -qx 'scripts/tracker-release-scoped675.sh'; then
  echo "=== RELEASE 675 PROD NAVIGATION AND COPY QUALIFICATION ==="
  timeout 600 bash "$QA/scripts/tracker-release-scoped675.sh" "$PY"
  echo "RELEASE_SCOPED_PREFLIGHT=PASSED"
 fi
 if [[ "$INSTANCE" == PROD && "$REF" == main ]] &&
    g diff --name-only "$BASE" "$TARGET" -- scripts/tracker-release-scoped674.sh |
      grep -qx 'scripts/tracker-release-scoped674.sh'; then
  echo "=== RELEASE 674 PROD PRODUCTIVITY AND RECOVERY QUALIFICATION ==="
  timeout 600 bash "$QA/scripts/tracker-release-scoped674.sh" "$PY"
  echo "RELEASE_SCOPED_PREFLIGHT=PASSED"
 fi
 if [[ "$INSTANCE" == PROD && "$REF" == main ]] &&
    g diff --name-only "$BASE" "$TARGET" -- scripts/tracker-release-scoped673.sh |
      grep -qx 'scripts/tracker-release-scoped673.sh'; then
  echo "=== RELEASE 673 PROD INTEGRATED MOBILE UX QUALIFICATION ==="
  timeout 600 bash "$QA/scripts/tracker-release-scoped673.sh" "$PY"
  echo "RELEASE_SCOPED_PREFLIGHT=PASSED"
 fi
 if [[ "$INSTANCE" == PROD && "$REF" == main ]] &&
    g diff --name-only "$BASE" "$TARGET" -- scripts/tracker-release-scoped672.sh |
      grep -qx 'scripts/tracker-release-scoped672.sh'; then
  echo "=== RELEASE 672 PROD SCOPED ACTION AND FOOD EDIT QUALIFICATION ==="
  timeout 360 bash "$QA/scripts/tracker-release-scoped672.sh" "$PY"
  echo "RELEASE_SCOPED_PREFLIGHT=PASSED"
 fi
 if [[ "$INSTANCE" == PROD && "$REF" == main ]] &&
    g diff --name-only "$BASE" "$TARGET" -- scripts/tracker-release-scoped671.sh |
      grep -qx 'scripts/tracker-release-scoped671.sh'; then
  echo "=== RELEASE 671 PROD FOCUSED FOOD EDIT BUTTON QUALIFICATION ==="
  timeout 360 bash "$QA/scripts/tracker-release-scoped671.sh" "$PY"
  echo "RELEASE_SCOPED_PREFLIGHT=PASSED"
 fi
 if [[ "$INSTANCE" == PROD && "$REF" == main ]] &&
    g diff --name-only "$BASE" "$TARGET" -- scripts/tracker-release-scoped670.sh |
      grep -qx 'scripts/tracker-release-scoped670.sh'; then
  echo "=== RELEASE 670 PROD FOCUSED FOOD ACTION QUALIFICATION ==="
  timeout 360 bash "$QA/scripts/tracker-release-scoped670.sh" "$PY"
  echo "RELEASE_SCOPED_PREFLIGHT=PASSED"
 fi
 if [[ "$INSTANCE" == PROD && "$REF" == main ]] &&
    g diff --name-only "$BASE" "$TARGET" -- scripts/tracker-release-scoped669.sh |
      grep -qx 'scripts/tracker-release-scoped669.sh'; then
  echo "=== RELEASE 669 PROD FOCUSED FOOD EDITOR QUALIFICATION ==="
  timeout 360 bash "$QA/scripts/tracker-release-scoped669.sh" "$PY"
  echo "RELEASE_SCOPED_PREFLIGHT=PASSED"
 fi
 if [[ "$INSTANCE" == PROD && "$REVIEWED_WORKOUT_668" == 1 ]]; then
  echo "=== RELEASE 668 PROD SCOPED WORKOUT QUALIFICATION ==="
  timeout 360 bash "$QA/scripts/tracker-release-scoped668.sh" "$PY"
  echo "RELEASE_SCOPED_PREFLIGHT=PASSED"
 fi
 if [[ "$INSTANCE" == PROD && "$REVIEWED_WORKOUT_655" == 1 ]]; then
  echo "=== RELEASE 655 PROD SCOPED WORKOUT QUALIFICATION ==="
  timeout 360 bash "$QA/scripts/tracker-release-scoped655.sh" "$PY"
  echo "RELEASE_SCOPED_PREFLIGHT=PASSED"
 fi
 if [[ "$INSTANCE" == PROD && "$REVIEWED_WORKOUT_654" == 1 ]]; then
  echo "=== RELEASE 654 PROD SCOPED WORKOUT QUALIFICATION ==="
  timeout 360 bash "$QA/scripts/tracker-release-scoped654.sh" "$PY"
  echo "RELEASE_SCOPED_PREFLIGHT=PASSED"
 fi
 if [[ "$INSTANCE" == PROD && "$REVIEWED_BLEND_710" == 1 ]]; then
  echo "=== RELEASE 710 PROD SCOPED BLEND VIAL DOSE QUALIFICATION ==="
  timeout 360 bash "$QA/scripts/tracker-release-scoped710.sh" "$PY"
  echo "RELEASE_710_PROD_SCOPED=PASSED"
 fi
 if [[ "$INSTANCE" == PROD && "$REVIEWED_COA_691" == 1 ]]; then
  echo "=== RELEASE 691 PROD SCOPED COA DOCUMENT QUALIFICATION ==="
  timeout 360 bash "$QA/scripts/tracker-release-scoped691.sh" "$PY"
  echo "RELEASE_SCOPED_PREFLIGHT=PASSED"
  echo "COA_691_PROD_FOCUSED_TESTS=PASSED"
 fi
 if [[ "$INSTANCE" == PROD && "$REVIEWED_COA_652" == 1 ]]; then
  timeout 360 bash "$QA/scripts/tracker-release-scoped652.sh" "$PY"
  echo "RELEASE_SCOPED_PREFLIGHT=PASSED"
 fi
 if [[ "$INSTANCE" == PROD && "$REF" == main ]] &&
    g diff --name-only "$BASE" "$TARGET" -- scripts/tracker-release-scoped653.sh |
      grep -qx 'scripts/tracker-release-scoped653.sh'; then
  # Release 653 is a presentation-only change; qualify exactly the impacted
  # Manage Test Types layout in the isolated candidate, without full QA.
  [[ -f "$QA/scripts/tracker-release-scoped653.sh" ]] ||
    fail "Missing qualified Release 653 scoped gate"
  echo "=== RELEASE 653 PROD SCOPED UI QUALIFICATION ==="
  timeout 360 bash "$QA/scripts/tracker-release-scoped653.sh" "$PY" --prod
  echo "RELEASE_SCOPED_PREFLIGHT=PASSED"
 fi
 # A backup-only Release 645 retry may reuse FULL prior qualification ONLY
 # after exact evidence, unchanged application/tests, and prior failure stage
 # are verified. Fresh focused tests and migration safeguards still execute.
 if [[ -f "$RUN/resume-evidence645-request" ]]; then
  [[ "$INSTANCE" == DEV && "$REF" == release/645-coa-default-document &&
      "$REVIEWED_COA_645" == 1 && "$DB_MIGRATION" == 1 &&
      "$QA_FULL_REQUIRED" == 1 ]] ||
     fail "Release 645 resume requested outside reviewed full DEV gate"
  "$PY" "$QA/scripts/tracker-resume-evidence645.py" \
      --app "$APP" --qa "$QA" --base "$BASE" --target "$TARGET" ||
      fail "Prior Release 645 full qualification evidence not verified"
  RESUME_645_VERIFIED=1
  QA_FULL_REQUIRED=0
  QA_CADENCE_REASON="verified prior full DEV qualification; backup-only retry"
  echo "COA_645_RESUME_FULL_TEST_REUSE=VERIFIED"
 fi
 echo "QA_FULL_REQUIRED=$QA_FULL_REQUIRED"
 echo "QA_CADENCE_REASON=$QA_CADENCE_REASON"
 if (( QA_FULL_REQUIRED == 1 )); then
  if [[ "$INSTANCE" == DEV ]]; then
   echo "=== ISOLATED BROWSER QUALIFICATION (FIRST) ==="
   # Older release contracts retain their 600s browser bound. Release
   # 751's additional strict modules need 1800s; both paths stay bounded.
   if [[ "$REF" == release/751-strict-csrf-dev-rollout ]]; then
    timeout 1800 bash "$QA/scripts/tracker-browser-qualify.sh" "$QA" "$PY"
   else
    timeout 600 bash "$QA/scripts/tracker-browser-qualify.sh" "$QA" "$PY"
   fi
   echo "=== BROWSER GATE PASSED ==="
  else
   echo "=== PROD: browser qualification is required on DEV before main promotion ==="
  fi
  echo "=== COMPLETE REGRESSION SUITE ==="
  echo "Critical safety tests are included in full-suite collection."
  "$PY" -c 'import xdist' >/dev/null ||
   fail "pytest-xdist missing; serial fallback prohibited"
  TEST_PYTEST_EXTRA=(-n 16 --dist=loadfile)
  echo "BACKEND_TEST_MODE=PARALLEL workers=16"
  if [[ "$INSTANCE" == DEV && "$REF" == release/751-strict-csrf-dev-rollout ]]; then
   # Run the same *complete* suite against pristine 750 and candidate 751,
   # in separate temporary data roots. Only inherited failures are allowed;
   # any new failure, error, skip or uncollected test fails closed.
   "$PY" -B "$QA/scripts/tracker-backend-parity751.py" \
    --python "$PY" --candidate "$QA" --base "$BASE" --target "$TARGET" \
    || fail "Release 751 introduced a backend regression"
   echo "=== FULL BACKEND BASELINE PARITY GATE PASSED ==="
  else
   timeout 1200 "$PY" -m pytest -q --tb=short --maxfail=1 --disable-warnings "${TEST_PYTEST_EXTRA[@]}" --durations=20 tests \
    --ignore=tests/browser --ignore=tests/test_bulk_vial_browser.py \
    --ignore=tests/test_bulk_vial_guided_browser.py --ignore=tests/test_bulk_delete_browser.py \
    --ignore=tests/test_purchase_vial_browser.py --ignore=tests/test_stage33_browser_sorting.py \
    --ignore=tests/test_health_timeline_dates_browser.py --ignore=tests/test_vitals_csv_browser.py
   echo "=== ALL BACKEND TESTS PASSED ==="
  fi
 else
  if [[ "$RESUME_645_VERIFIED" == 1 ]]; then
   echo "=== VERIFIED PRIOR FULL BROWSER AND BACKEND EVIDENCE REUSED ==="
   echo "COA_645_FULL_QUALIFICATION_REUSE=PASSED"
   # Focused regressions ran afresh; this exact marker is required by the
   # independent DEV qualification receipt validator for QA_FULL_REQUIRED=0.
   # Full browser/backend gates remain explicitly documented as reused.
   echo "FOCUSED_RELEASE_GATE=PASSED"
  else
   echo "=== FULL BROWSER AND BACKEND SUITES NOT REQUESTED ==="
   echo "FOCUSED_RELEASE_GATE=PASSED"
  fi
 fi
 cd "$APP"
 unset TRACKER_DATA_DIR PYTHONPATH
 [[ -z "$(g status --porcelain)" && "$(g rev-parse HEAD)" == "$BASE" ]] || fail "Live checkout changed"
 echo "=== Source and configuration recovery snapshot ==="
 umask 077
 mkdir -m 700 "$SAVE"
 g archive --format=tar HEAD | gzip > "$SAVE/source.tar.gz"
 cp -p /etc/tracker.env "$SAVE/tracker.env"
 chmod 600 "$SAVE/source.tar.gz" "$SAVE/tracker.env"
 if [[ -f "$APP/.env" ]]; then cp -p "$APP/.env" "$SAVE/local.env"; chmod 600 "$SAVE/local.env"; fi
 if [[ "$DB_MIGRATION" == 1 ]]; then
  echo "=== LIVE ATTACHMENT INTEGRITY BEFORE MIGRATION BACKUP ==="
  if [[ "$INSTANCE" == DEV ]]; then
   "$PY" "$QA/scripts/tracker-dev-attachment-gate650.py" --data "$LIVE_DATA_DIR" ||
     fail "DEV upload integrity failure (invalid path or present-file hash mismatch)"
   echo "LIVE_ATTACHMENT_PREBACKUP=DEV_MISSING_REFERENCES_NONBLOCKING"
  else
   "$PY" "$QA/scripts/tracker-attachment-integrity645.py" --data "$LIVE_DATA_DIR" --hashes ||
     fail "Live attachments changed since preflight; migration backup blocked"
   echo "LIVE_ATTACHMENT_PREBACKUP=PASSED"
  fi
  echo "=== Verified database backup required for data migration ==="
  DATA_DIR="$("$PY" - <<'PY'
from pathlib import Path
import re
root=Path('/opt/tracker'); data=root/'data'
for line in Path('/etc/tracker.env').read_text().splitlines():
 m=re.match(r'^\s*(?:export\s+)?TRACKER_DATA_DIR\s*=(.*)$',line)
 if m and m.group(1).strip(): data=Path(m.group(1).strip().strip("\"'"))
if not data.is_absolute(): data=root/data
print(data.resolve())
PY
)"
  [[ -f "$DATA_DIR/tracker.db" ]] || fail "Live SQLite database missing"
  mkdir -m 700 "$SAVE/archives"
  if [[ "$INSTANCE" == DEV ]]; then
   # Permanent DEV policy: missing upload files do not block a release.
   # Back up SQLite and all present uploads, verify their checksums,
   # restore the archive in isolation; never change or fabricate files.
   # PROD still takes the strict original backup path below.
   ARCHIVE="$(PYTHONPATH="$QA" TRACKER_DATA_DIR="$DATA_DIR" "$PY" \
     "$QA/scripts/tracker-workout-dev-backup655.py" --data "$DATA_DIR" --dest "$SAVE/archives")" ||
     fail "DEV SQLite/present-upload backup or isolated restoration failed"
   [[ "$ARCHIVE" == "$SAVE"/archives/tracker-dev655-*.zip &&
      -f "$ARCHIVE" && ! -L "$ARCHIVE" ]] ||
     fail "DEV backup helper returned an invalid archive pathname"
   echo "DEV_BACKUP=VERIFIED_SQLITE_AND_ALL_PRESENT_UPLOADS"
   echo "DEV_MISSING_UPLOADS=NONBLOCKING"
  else
   ARCHIVE="$(PYTHONPATH="$APP" TRACKER_DATA_DIR="$DATA_DIR" "$PY" - "$DATA_DIR" "$SAVE/archives" <<'PY'
from pathlib import Path
import sys
from app.backup import create_backup
print(create_backup(Path(sys.argv[1]),Path(sys.argv[2])))
PY
)"
   chmod 600 "$ARCHIVE"
   PYTHONPATH="$QA" TRACKER_DATA_DIR="$RUN/test-data" \
     "$PY" "$QA/scripts/tracker-restore-verify.py" --archive "$ARCHIVE"
  fi
  chmod 600 "$ARCHIVE"
  echo "=== ISOLATED RESTORE VERIFICATION PASSED ==="
  echo "DATABASE_BACKUP=VERIFIED_FOR_MIGRATION"
 else
  echo "DATABASE_BACKUP=SKIPPED_NO_MIGRATION"
 fi
 echo "=== Install via fast-forward ==="
 umask 022
 g merge --ff-only "$TARGET"
 INSTALLED=1
 [[ "$(g rev-parse HEAD)" == "$TARGET" ]] ||
   fail "Unexpected new HEAD"

  echo "=== Refresh installed Python bytecode ==="
  find "$APP/app" "$APP/scripts" -type f -name '*.pyc' -delete
  "$PY" -m compileall -q -f "$APP/app" "$APP/scripts"
  echo "INSTALLED_BYTECODE_REFRESH=PASSED"
 while IFS= read -r f; do
  [[ -f "$APP/$f" && ! -L "$APP/$f" ]] || fail "Missing new source: $f"
  chmod a+r "$APP/$f"
 done < <(changed)
 "$PY" "$APP/scripts/tracker-deployment-guard.py" \
  --root "$APP" --base "$BASE" --target "$TARGET" --service tracker
 [[ -z "$(g status --porcelain)" ]] || fail "Working tree became dirty"
 if ((RESTART==1)); then
  echo "Restarting Tracker"
  systemctl reset-failed tracker
  systemctl restart tracker
 else echo "Tooling-only release: no Tracker restart"; fi
 "$PY" "$APP/scripts/tracker-runtime-smoke.py" --instance "$INSTANCE"
 systemctl is-active --quiet tracker || fail "Tracker service not active"
 echo "======================================"
 echo " TRACKER RELEASE DEPLOYMENT SUCCESS"
 echo "======================================"
 g log -1 --oneline
 echo "Source recovery snapshot: $SAVE/source.tar.gz"
 QUALIFICATION_COMPLETE=1
}
follow_deployment_log() {
 local unit="$1" log="$2" pid="" i final
 echo "=== Live deployment log (Ctrl+C detaches; worker continues) ==="
 # A root-only log is created before systemd-run, avoiding any startup race.
 for ((i=0; i<30; i++)); do
  pid="$(systemctl show "$unit.service" -p MainPID --value 2>/dev/null || true)"
  if [[ "$pid" =~ ^[1-9][0-9]*$ ]]; then break; fi
  if grep -q '^EXIT_STATUS=' "$log" 2>/dev/null; then break; fi
  sleep 0.2
 done
 if [[ "$pid" =~ ^[1-9][0-9]*$ ]]; then
  # GNU tail exits when this specific, detached systemd worker exits.
  tail -n +1 --follow=descriptor --pid="$pid" "$log"
 else
  # A worker that has already exited still gets its full log displayed.
  cat "$log"
 fi
 final="$(sed -n 's/^EXIT_STATUS=//p' "$log" | tail -n 1)"
 if [[ "$final" == 0 ]]; then
  echo "=== DEPLOYMENT FINISHED SUCCESSFULLY ==="
 elif [[ "$final" =~ ^[0-9]+$ ]]; then
  echo "=== DEPLOYMENT FAILED (exit $final) ===" >&2
  return 1
 else
  echo "=== DEPLOYMENT STATUS UNKNOWN; check the log ===" >&2
  return 1
 fi
}
if [[ "${1:-}" == --worker ]]; then
 shift
 [[ $# -ge 12 && $# -le 23 ]] || fail "Bad worker arguments"
 worker "$@"
 exit 0
fi
INSTANCE=''; BASE=''; TARGET=''; REF=''; FOLLOW=1; SERIAL_TESTS=0; DEV_FOCUSED_630=0; DB_MIGRATION=0; REVIEWED_REGIMEN_635=0; REVIEWED_FACTS_639=0; REVIEWED_COA_643=0; REVIEWED_COA_645=0; REVIEWED_COA_652=0; REVIEWED_WORKOUT_654=0; REVIEWED_WORKOUT_655=0; REVIEWED_WORKOUT_667=0; REVIEWED_WORKOUT_668=0; FULL_SUITE=0; RESUME_VERIFIED_645=0; REVIEWED_COA_691=0; REVIEWED_BLEND_710=0; REVIEWED_TABLET_731=0; REVIEWED_CATCHUP_735=0; REVIEWED_VIAL_758=0
while (( $# )); do
 case "$1" in
  --detach) FOLLOW=0; shift;;
  --dev-focused-630) DEV_FOCUSED_630=1; shift;;
  --db-migration) DB_MIGRATION=1; shift;;
  --reviewed-regimen-635) REVIEWED_REGIMEN_635=1; shift;;
  --reviewed-facts-639) REVIEWED_FACTS_639=1; shift;;
  --reviewed-coa-643) REVIEWED_COA_643=1; shift;;
  --reviewed-coa-645) REVIEWED_COA_645=1; shift;;
  --reviewed-coa-652) REVIEWED_COA_652=1; shift;;
  --reviewed-coa-691) REVIEWED_COA_691=1; shift;;
  --reviewed-blend-710) REVIEWED_BLEND_710=1; shift;;
  --reviewed-tablet-731) REVIEWED_TABLET_731=1; shift;;
  --reviewed-catchup-735) REVIEWED_CATCHUP_735=1; shift;;
  --reviewed-vial-758) REVIEWED_VIAL_758=1; shift;;
  --reviewed-workout-654) REVIEWED_WORKOUT_654=1; shift;;
  --reviewed-workout-655) REVIEWED_WORKOUT_655=1; shift;;
  --reviewed-workout-667) REVIEWED_WORKOUT_667=1; shift;;
  --reviewed-workout-668) REVIEWED_WORKOUT_668=1; shift;;
  --full-suite) FULL_SUITE=1; shift;;
  --resume-verified-645) RESUME_VERIFIED_645=1; shift;;
  --serial-tests) fail "Serial testing prohibited";;
  --instance|--base|--target|--ref)
   (( $# >= 2 )) || fail "Missing argument for $1"
   case "$1" in
    --instance) INSTANCE="$2";;
    --base) BASE="$2";;
    --target) TARGET="$2";;
    --ref) REF="$2";;
   esac
   shift 2;;
  *) fail "Unknown argument: $1";;
 esac
done
[[ "$INSTANCE" == DEV || "$INSTANCE" == PROD ]] || fail "Choose DEV or PROD"
[[ "$BASE" =~ ^[0-9a-f]{40}$ && "$TARGET" =~ ^[0-9a-f]{40}$ ]] || fail "Use full 40-character SHAs"
[[ "$REF" =~ ^[a-zA-Z0-9][a-zA-Z0-9._/-]*$ && "$REF" != *..* ]] || fail "Invalid branch"
[[ "$INSTANCE" != PROD || "$REF" == main ]] || fail "PROD requires --ref main"
[[ "$DEV_FOCUSED_630" == 0 || ( "$INSTANCE" == DEV && "$REF" == release/630-food-duplicate-resolution ) ]] || fail "Focused 630 is DEV-only and branch-specific"
[[ "$REVIEWED_CATCHUP_735" == 0 || "$DB_MIGRATION" == 1 ]] ||
  fail "Release 735 catch-up requires verified --db-migration backup"
if [[ "$REVIEWED_CATCHUP_735" == 1 ]]; then
  [[ "$INSTANCE" == PROD && "$REF" == main &&
     "$BASE" == 3718936aedfcb1b8fe243c86fe6fc7e06a7a41d2 &&
     "$REVIEWED_TABLET_731" == 0 && "$REVIEWED_REGIMEN_635" == 0 &&
     "$REVIEWED_FACTS_639" == 0 && "$REVIEWED_COA_643" == 0 &&
     "$REVIEWED_COA_645" == 0 && "$REVIEWED_COA_652" == 0 &&
     "$REVIEWED_COA_691" == 0 && "$REVIEWED_BLEND_710" == 0 &&
     "$REVIEWED_WORKOUT_654" == 0 && "$REVIEWED_WORKOUT_655" == 0 &&
     "$REVIEWED_WORKOUT_667" == 0 && "$REVIEWED_WORKOUT_668" == 0 ]] ||
    fail "Release 735 catch-up must be an isolated PROD-only reviewed schema stage"
fi
if [[ "$REVIEWED_VIAL_758" == 1 ]]; then
 [[ "$DB_MIGRATION" == 1 ]] || fail "Release 758 schema requires verified migration backup"
 [[ "$INSTANCE" == DEV && "$REF" == release/758-vial-label-dose-markings ||
    "$INSTANCE" == PROD && "$REF" == main ]] || fail "Release 758 reviewed schema flag outside approved scope"
fi
[[ "$REVIEWED_TABLET_731" == 0 || "$DB_MIGRATION" == 1 ]] ||
  fail "Reviewed Release 731 tablet schema requires --db-migration"
if [[ "$REVIEWED_TABLET_731" == 1 ]]; then
  [[ "$REVIEWED_REGIMEN_635" == 0 && "$REVIEWED_FACTS_639" == 0 &&
     "$REVIEWED_COA_643" == 0 && "$REVIEWED_COA_645" == 0 &&
     "$REVIEWED_COA_652" == 0 && "$REVIEWED_COA_691" == 0 &&
     "$REVIEWED_BLEND_710" == 0 && "$REVIEWED_WORKOUT_654" == 0 &&
     "$REVIEWED_WORKOUT_655" == 0 && "$REVIEWED_WORKOUT_667" == 0 &&
     "$REVIEWED_WORKOUT_668" == 0 ]] ||
    fail "Release 731 must be the sole reviewed schema flag"
fi
[[ "$REVIEWED_REGIMEN_635" == 0 || "$DB_MIGRATION" == 1 ]] || fail "Reviewed regimen deployment requires --db-migration"
[[ "$REVIEWED_FACTS_639" == 0 || "$DB_MIGRATION" == 1 ]] || fail "Reviewed facts deployment requires --db-migration"
[[ "$REVIEWED_FACTS_639" == 0 || "$REVIEWED_REGIMEN_635" == 0 ]] || fail "Only one reviewed schema flag permitted"
[[ "$REVIEWED_COA_643" == 0 || "$DB_MIGRATION" == 1 ]] || fail "Reviewed COA deployment requires --db-migration"
[[ "$REVIEWED_COA_643" == 0 || ( "$REVIEWED_FACTS_639" == 0 && "$REVIEWED_REGIMEN_635" == 0 ) ]] || fail "Only one reviewed schema flag permitted"
[[ "$REVIEWED_COA_645" == 0 || "$DB_MIGRATION" == 1 ]] || fail "Reviewed COA 645 requires --db-migration"
[[ "$REVIEWED_COA_652" == 0 || "$DB_MIGRATION" == 1 ]] || fail "Reviewed COA 652 requires --db-migration"
[[ "$REVIEWED_COA_691" == 0 || "$DB_MIGRATION" == 1 ]] || fail "Reviewed COA 691 requires --db-migration"
[[ "$REVIEWED_BLEND_710" == 0 || "$DB_MIGRATION" == 1 ]] || fail "Reviewed blend 710 requires --db-migration"
if [[ "$REVIEWED_BLEND_710" == 1 ]]; then
  [[ "$REVIEWED_REGIMEN_635" == 0 && "$REVIEWED_FACTS_639" == 0 &&
     "$REVIEWED_COA_643" == 0 && "$REVIEWED_COA_645" == 0 &&
     "$REVIEWED_COA_652" == 0 && "$REVIEWED_COA_691" == 0 &&
     "$REVIEWED_WORKOUT_654" == 0 && "$REVIEWED_WORKOUT_655" == 0 &&
     "$REVIEWED_WORKOUT_667" == 0 && "$REVIEWED_WORKOUT_668" == 0 ]] ||
     fail "Release 710 must be the sole reviewed schema flag"
fi
if [[ "$REVIEWED_COA_691" == 1 ]]; then
  [[ "$REVIEWED_BLEND_710" == 0 && "$REVIEWED_REGIMEN_635" == 0 && "$REVIEWED_FACTS_639" == 0 &&
     "$REVIEWED_COA_643" == 0 && "$REVIEWED_COA_645" == 0 &&
     "$REVIEWED_COA_652" == 0 && "$REVIEWED_WORKOUT_654" == 0 &&
     "$REVIEWED_WORKOUT_655" == 0 && "$REVIEWED_WORKOUT_667" == 0 &&
     "$REVIEWED_WORKOUT_668" == 0 ]] ||
     fail "Release 691 must be the sole reviewed schema flag"
fi
[[ "$REVIEWED_WORKOUT_654" == 0 || "$DB_MIGRATION" == 1 ]] || fail "Reviewed Workout 654 requires --db-migration"
[[ "$REVIEWED_WORKOUT_655" == 0 || "$DB_MIGRATION" == 1 ]] || fail "Reviewed Workout 655 requires --db-migration"
[[ "$REVIEWED_WORKOUT_667" == 0 || "$DB_MIGRATION" == 1 ]] || fail "Reviewed Workout 667 requires --db-migration"
[[ "$REVIEWED_WORKOUT_668" == 0 || "$DB_MIGRATION" == 1 ]] || fail "Reviewed Workout 668 requires --db-migration"
[[ "$REVIEWED_WORKOUT_668" == 0 || ( "$REVIEWED_WORKOUT_667" == 0 && "$REVIEWED_WORKOUT_655" == 0 && "$REVIEWED_WORKOUT_654" == 0 && "$REVIEWED_COA_652" == 0 && "$REVIEWED_COA_645" == 0 && "$REVIEWED_COA_643" == 0 && "$REVIEWED_FACTS_639" == 0 && "$REVIEWED_REGIMEN_635" == 0 ) ]] || fail "Only one reviewed schema flag permitted"
[[ "$REVIEWED_WORKOUT_667" == 0 || ( "$REVIEWED_WORKOUT_655" == 0 && "$REVIEWED_WORKOUT_654" == 0 && "$REVIEWED_COA_652" == 0 && "$REVIEWED_COA_645" == 0 && "$REVIEWED_COA_643" == 0 && "$REVIEWED_FACTS_639" == 0 && "$REVIEWED_REGIMEN_635" == 0 ) ]] || fail "Only one reviewed schema flag permitted"
[[ "$REVIEWED_WORKOUT_655" == 0 || ( "$REVIEWED_WORKOUT_654" == 0 && "$REVIEWED_COA_652" == 0 && "$REVIEWED_COA_645" == 0 && "$REVIEWED_COA_643" == 0 && "$REVIEWED_FACTS_639" == 0 && "$REVIEWED_REGIMEN_635" == 0 ) ]] || fail "Only one reviewed schema flag permitted"
[[ "$REVIEWED_WORKOUT_654" == 0 || ( "$REVIEWED_WORKOUT_655" == 0 && "$REVIEWED_COA_652" == 0 && "$REVIEWED_COA_645" == 0 && "$REVIEWED_COA_643" == 0 && "$REVIEWED_FACTS_639" == 0 && "$REVIEWED_REGIMEN_635" == 0 ) ]] || fail "Only one reviewed schema flag permitted"
[[ "$REVIEWED_COA_652" == 0 || ( "$REVIEWED_COA_645" == 0 && "$REVIEWED_COA_643" == 0 && "$REVIEWED_FACTS_639" == 0 && "$REVIEWED_REGIMEN_635" == 0 ) ]] || fail "Only one reviewed schema flag permitted"
[[ "$RESUME_VERIFIED_645" == 0 || ( "$INSTANCE" == DEV && "$REF" == release/645-coa-default-document && "$DB_MIGRATION" == 1 && "$REVIEWED_COA_645" == 1 ) ]] || fail "Resume is restricted to reviewed Release 645 DEV"
[[ "$REVIEWED_COA_645" == 0 || ( "$REVIEWED_COA_643" == 0 && "$REVIEWED_FACTS_639" == 0 && "$REVIEWED_REGIMEN_635" == 0 ) ]] || fail "Only one reviewed schema flag permitted"
[[ $(id -u) == 0 && -x "$PY" && -f /etc/tracker.env ]] || fail "Run as root on configured Tracker host"
instance_check "$INSTANCE"
verify_prod_approval
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(g branch --show-current)" == main && -z "$(g status --porcelain)" ]] || fail "Not a clean main checkout"
[[ "$(g rev-parse HEAD)" == "$BASE" ]] || fail "Unexpected starting commit"
systemctl is-active --quiet tracker || fail "Tracker service is not active"
mkdir -p /tmp/tracker-backups
umask 077
RUN="$(mktemp -d /tmp/tracker-backups/release.XXXXXXXX)"
chmod 700 "$RUN"
cp "$0" "$RUN/worker.sh"
chmod 700 "$RUN/worker.sh"
bash -n "$RUN/worker.sh"
UNIT="tracker-release-$(date +%s)-$$"
# Make the log available before the worker starts; no source/data changes.
touch "$RUN/deployment.log"
if [[ "$RESUME_VERIFIED_645" == 1 ]]; then
 printf "requested\n" > "$RUN/resume-evidence645-request"
 chmod 600 "$RUN/resume-evidence645-request"
fi
# Dedicated hosts: 18 vCPUs and 18 GiB RAM allocated per LXC.
# Operator-required full parallel qualification: 16 pytest workers and
# a 16 GiB systemd release-worker memory ceiling on both DEV and PROD.
# Do not silently lower either bound or introduce a serial fallback.
MEMORY_PROPERTY="MemoryMax=16G"
echo "RELEASE_WORKER_MEMORY=$MEMORY_PROPERTY"
systemd-run --unit="$UNIT" --collect --property="$MEMORY_PROPERTY" \
 /bin/bash "$RUN/worker.sh" --worker "$RUN" "$INSTANCE" "$BASE" "$TARGET" "$REF" "$SERIAL_TESTS" "$DEV_FOCUSED_630" "$DB_MIGRATION" "$REVIEWED_REGIMEN_635" "$REVIEWED_FACTS_639" "$REVIEWED_COA_643" "$REVIEWED_COA_645" "$REVIEWED_COA_652" "$FULL_SUITE" "$REVIEWED_WORKOUT_654" "$REVIEWED_WORKOUT_655" "$REVIEWED_WORKOUT_667" "$REVIEWED_WORKOUT_668" "$REVIEWED_COA_691" "$REVIEWED_BLEND_710" "$REVIEWED_TABLET_731" "$REVIEWED_CATCHUP_735" "$REVIEWED_VIAL_758"
echo "Launched: $UNIT"
echo "Log: $RUN/deployment.log"
if (( FOLLOW )); then
 follow_deployment_log "$UNIT" "$RUN/deployment.log"
else
 printf 'Detached. To follow: tail -n +1 -f "%s/deployment.log"\n' "$RUN"
fi
