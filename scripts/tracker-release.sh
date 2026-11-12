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
 RUN="$1"; INSTANCE="$2"; BASE="$3"; TARGET="$4"; REF="$5"; SERIAL_TESTS="$6"
 [[ "$SERIAL_TESTS" == 0 ]] || fail "Invalid serial test override"
 QA="$RUN/source"; SAVE="$RUN/pre-deployment"; INSTALLED=0; RESTART=0
 export GIT_CONFIG_COUNT=2
 export GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
 export GIT_CONFIG_KEY_1=safe.directory GIT_CONFIG_VALUE_1="$QA"
 umask 022
 exec >> "$RUN/deployment.log" 2>&1
 trap cleanup EXIT
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
 if g diff --name-only "$BASE" "$TARGET" | grep -Eq '^(deploy/|requirements[^/]*|alembic/|alembic.ini|app/(db|models|migrations).py)'; then
  fail "Schema/dependency/systemd changes require separately reviewed deployment"
 fi
 RESTART=0
 [[ -z "$(changed)" ]] || RESTART=1
 echo "=== Isolated source tests ==="
 g worktree add --detach "$QA" "$TARGET"
 cd "$QA"
 export TRACKER_DATA_DIR="$RUN/test-data" PYTHONPATH="$QA"
 mkdir -p "$TRACKER_DATA_DIR"
 git diff --check "$BASE" "$TARGET"
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
 if [[ "$INSTANCE" == DEV ]]; then
  echo "=== ISOLATED BROWSER QUALIFICATION (FIRST) ==="
  timeout 600 bash "$QA/scripts/tracker-browser-qualify.sh" "$QA" "$PY"
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
 timeout 1200 "$PY" -m pytest -q --tb=short --maxfail=1 --disable-warnings "${TEST_PYTEST_EXTRA[@]}" --durations=20 tests \
  --ignore=tests/browser --ignore=tests/test_bulk_vial_browser.py \
  --ignore=tests/test_bulk_vial_guided_browser.py --ignore=tests/test_bulk_delete_browser.py \
  --ignore=tests/test_purchase_vial_browser.py --ignore=tests/test_stage33_browser_sorting.py \
  --ignore=tests/test_health_timeline_dates_browser.py --ignore=tests/test_vitals_csv_browser.py
 echo "=== ALL BACKEND TESTS PASSED ==="
 cd "$APP"
 unset TRACKER_DATA_DIR PYTHONPATH
 [[ -z "$(g status --porcelain)" && "$(g rev-parse HEAD)" == "$BASE" ]] || fail "Live checkout changed"
 echo "=== Verified source and data recovery backup ==="
 umask 077
 mkdir -m 700 "$SAVE"
 g archive --format=tar HEAD | gzip > "$SAVE/source.tar.gz"
 cp -p /etc/tracker.env "$SAVE/tracker.env"
 chmod 600 "$SAVE/source.tar.gz" "$SAVE/tracker.env"
 if [[ -f "$APP/.env" ]]; then cp -p "$APP/.env" "$SAVE/local.env"; chmod 600 "$SAVE/local.env"; fi
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
 echo "=== ISOLATED RESTORE VERIFICATION PASSED ==="
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
 echo "Verified recovery archive: $ARCHIVE"
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
 [[ $# -eq 6 ]] || fail "Bad worker arguments"
 worker "$@"
 exit 0
fi
INSTANCE=''; BASE=''; TARGET=''; REF=''; FOLLOW=1; SERIAL_TESTS=0
while (( $# )); do
 case "$1" in
  --detach) FOLLOW=0; shift;;
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
# DEV and PROD have matching 8 GiB LXC allocations. Parallel release
# workers get 6 GiB, leaving 2 GiB for the running Tracker service and OS.
# --serial-tests retains the original conservative 1 GiB release limit.
if [[ "$SERIAL_TESTS" == 0 ]]; then
 MEMORY_PROPERTY="MemoryMax=6G"
else
 MEMORY_PROPERTY="MemoryMax=1G"
fi
echo "RELEASE_WORKER_MEMORY=$MEMORY_PROPERTY"
systemd-run --unit="$UNIT" --collect --property="$MEMORY_PROPERTY" \
 /bin/bash "$RUN/worker.sh" --worker "$RUN" "$INSTANCE" "$BASE" "$TARGET" "$REF" "$SERIAL_TESTS"
echo "Launched: $UNIT"
echo "Log: $RUN/deployment.log"
if (( FOLLOW )); then
 follow_deployment_log "$UNIT" "$RUN/deployment.log"
else
 printf 'Detached. To follow: tail -n +1 -f "%s/deployment.log"\n' "$RUN"
fi
