#!/usr/bin/env bash
# Release 498: isolated, offline browser qualification for a candidate worktree.
# Only localhost; never reads /etc/tracker.env or the installed Tracker database.
set -Eeuo pipefail
umask 077

# Release 584: an explicit, restricted fast path. The normal two-argument
# guarded qualification retains its full set of browser gates unchanged.
MODE=full
TARGETED_MODULE=""
if [[ $# == 4 && "${3:-}" == --targeted-strict ]]; then
  MODE=targeted
  TARGETED_MODULE="$4"
  [[ "$TARGETED_MODULE" == csrf-batch589 || "$TARGETED_MODULE" =~ ^tests/browser/test_(csrf_preparations583|form_overlap586|csrf_bulk587|csrf_multipart588)[.]py$ ]] || \
  [[ "$TARGETED_MODULE" == csrf-batch627 || "$TARGETED_MODULE" == csrf-positive627 || "$TARGETED_MODULE" == csrf-new627 ]] || \
  [[ "$TARGETED_MODULE" == note-title575 || "$TARGETED_MODULE" == quick603 || "$TARGETED_MODULE" == workflows580 || "$TARGETED_MODULE" == blend-vial710 || "$TARGETED_MODULE" == blend-correction711 || "$TARGETED_MODULE" == u100-withdraw712 || "$TARGETED_MODULE" == global-time24-713 || "$TARGETED_MODULE" == coa-untested715 || "$TARGETED_MODULE" == workout-active716 || "$TARGETED_MODULE" == workout-completed717 || "$TARGETED_MODULE" == workout-machine718 || "$TARGETED_MODULE" == workout-manage719 ]] || {
    echo "ERROR: Targeted module must be one of the audited CSRF batch or 583/586/587/588 fixtures" >&2
    exit 2
  }
elif [[ $# != 2 ]]; then
  echo "Usage: tracker-browser-qualify.sh SOURCE PYTHON [--targeted-strict MODULE]" >&2
  exit 2
fi
SOURCE="$(cd "$1" && pwd -P)"
PY="$2"
[[ "$SOURCE" != /opt/tracker && -f "$SOURCE/app/main.py" && -x "$PY" ]] || {
  echo "ERROR: Source must be a separate candidate worktree and Python must exist" >&2
  exit 2
}
# HTMX is intentionally gitignored and absent from detached worktrees.
# Use only the already-installed local vendor asset, never download code
# or read application credentials/configuration.
VENDOR_SRC="/opt/tracker/app/static/vendor/htmx.min.js"
VENDOR_DST="$SOURCE/app/static/vendor/htmx.min.js"
[[ -f "$VENDOR_SRC" && ! -L "$VENDOR_SRC" ]] || {
  echo "ERROR: Trusted installed HTMX asset unavailable" >&2
  exit 2
}

if [[ -e "$VENDOR_DST" || -L "$VENDOR_DST" ]]; then
  [[ -f "$VENDOR_DST" && ! -L "$VENDOR_DST" ]] || {
    echo "ERROR: Existing candidate HTMX asset is not a regular file" >&2
    exit 2
  }

  cmp -s "$VENDOR_SRC" "$VENDOR_DST" || {
    echo "ERROR: Existing candidate HTMX asset differs from trusted source" >&2
    exit 2
  }

  echo "ISOLATED_HTMX_VENDOR=REUSED_VERIFIED"
else
  mkdir -p "$(dirname "$VENDOR_DST")"

  install -m 0644 "$VENDOR_SRC" "$VENDOR_DST"

  cmp -s "$VENDOR_SRC" "$VENDOR_DST" || {
    echo "ERROR: Copied isolated HTMX asset differs from trusted source" >&2
    exit 2
  }

  echo "ISOLATED_HTMX_VENDOR=COPIED_VERIFIED"
fi

echo "ISOLATED_HTMX_VENDOR=VERIFIED"
# Release 705: fail fast on all 51 tracked app callsites and the
# explicitly unqualified Release 668 workout POST before launching browsers.
cd "$SOURCE"
"$PY" -B -m pytest -q --tb=short --maxfail=1 \
  tests/test_release579_csrf_runtime_report.py::test_579_two_tracked_javascript_callsites_not_overclaimed \
  tests/test_release579_csrf_runtime_report.py::test_705_668_offline_sync_is_explicitly_pending_positive_browser_evidence \
  tests/test_release579_csrf_runtime_report.py::test_705_668_offline_sync_request_is_reviewed_not_witnessed
echo 'RELEASE_705_579_TRACKED_JS_PREFLIGHT=PASSED'
ROOT="$(mktemp -d /tmp/tracker-browser-qa.XXXXXXXX)"
DATA="$ROOT/data"
mkdir -m 700 "$DATA"
SERVER_LOG="$ROOT/server.log"
TLS_LOG="$ROOT/tls-proxy.log"
TEST_LOG="$ROOT/pytest-browser.log"
SERVER_PID=""
TLS_PID=""

cleanup() {
  local code=$?
  trap - EXIT
  if [[ -n "$TLS_PID" ]]; then
    kill "$TLS_PID" 2>/dev/null || true
    wait "$TLS_PID" 2>/dev/null || true
  fi
  if [[ -n "$SERVER_PID" ]]; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
  # Test-only TLS identity must not persist after the proxy stops.
  rm -f "$ROOT/qa-private-key.pem" "$ROOT/qa-cert.pem"
  echo "ISOLATED_SERVER_STOPPED=YES"
  if ((code != 0)); then
    echo "ISOLATED_BROWSER=FAILED code=$code"
    echo "BROWSER_TEST_LOG=$TEST_LOG"
    if [[ -f "$TEST_LOG" ]]; then
      echo "=== BROWSER FAILURE SUMMARY ==="
      grep -E '^(FAILED |ERROR |E   |[0-9]+ failed|[0-9]+ error)' "$TEST_LOG" | tail -n 35 || true
    fi
    echo "SERVER_LOG=$SERVER_LOG"
    tail -n 15 "$SERVER_LOG" 2>/dev/null || true
    echo "TLS_LOG=$TLS_LOG"
    tail -n 10 "$TLS_LOG" 2>/dev/null || true
  else
    echo "ISOLATED_BROWSER=PASSED"
  fi
  exit "$code"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

cd "$SOURCE"
PORT="$("$PY" - <<'PY'
import socket
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
)"
URL="http://127.0.0.1:$PORT"

echo "=== ISOLATED CANDIDATE SERVER ==="
echo "CANDIDATE_COMMIT=$(git rev-parse HEAD)"
echo "CANDIDATE_URL=$URL"

env -i HOME=/root PATH=/usr/local/bin:/usr/bin:/bin \
  PYTHONPATH="$SOURCE" TRACKER_DATA_DIR="$DATA" TRACKER_INSTANCE=DEV \
  PYTHONDONTWRITEBYTECODE=1 \
  "$PY" -B -m uvicorn app.main:app --host 127.0.0.1 \
    --port "$PORT" --app-dir "$SOURCE" > "$SERVER_LOG" 2>&1 &
SERVER_PID=$!

"$PY" - "$URL" "$SERVER_PID" <<'PY'
import os
import sys
import time
import urllib.error
import urllib.request

url, pid = sys.argv[1], int(sys.argv[2])
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
for _ in range(60):
    try:
        os.kill(pid, 0)
        with opener.open(url + "/healthz", timeout=2) as response:
            if response.status != 200 or b'"ok":true' not in response.read().replace(b' ', b''):
                raise RuntimeError("Unexpected candidate health response")
        with opener.open(url + "/", timeout=5) as response:
            html = response.read()
            if response.status == 200 and b'id="nav-sortable"' in html:
                print("ISOLATED_SERVER_READY=YES")
                break
    except (OSError, urllib.error.URLError, RuntimeError):
        time.sleep(0.5)
else:
    raise SystemExit("ERROR: Isolated candidate did not become ready")
PY

echo "=== ISOLATED HTTPS REVERSE PROXY ==="
command -v openssl >/dev/null || {
  echo "ERROR: openssl is required for local HTTPS QA" >&2
  exit 2
}
HTTPS_PORT="$("$PY" - <<'PY'
import socket
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
)"
HTTPS_URL="https://127.0.0.1:$HTTPS_PORT"
openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
  -subj '/CN=127.0.0.1' \
  -addext 'subjectAltName=IP:127.0.0.1' \
  -keyout "$ROOT/qa-private-key.pem" -out "$ROOT/qa-cert.pem" \
  >"$ROOT/openssl.log" 2>&1
env -i HOME=/root PATH=/usr/local/bin:/usr/bin:/bin \
  PYTHONDONTWRITEBYTECODE=1 \
  "$PY" -B scripts/tracker-tls-proxy501.py \
  --listen-port "$HTTPS_PORT" --backend-port "$PORT" \
  --qa-rewrite-browser-host \
  --cert "$ROOT/qa-cert.pem" --key "$ROOT/qa-private-key.pem" \
  >"$TLS_LOG" 2>&1 &
TLS_PID=$!

"$PY" - "$HTTPS_URL" "$TLS_PID" <<'PY'
import os
import ssl
import sys
import time
import urllib.error
import urllib.request

url, pid = sys.argv[1], int(sys.argv[2])
context = ssl._create_unverified_context()  # Ephemeral test-only certificate.
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
    urllib.request.HTTPSHandler(context=context))
for _ in range(60):
    try:
        os.kill(pid, 0)
        with opener.open(url + "/healthz", timeout=2) as response:
            assert response.status == 200
            assert b'"ok":true' in response.read().replace(b' ', b'')
        print("ISOLATED_HTTPS_PROXY_READY=YES")
        break
    except (OSError, urllib.error.URLError, AssertionError):
        time.sleep(0.5)
else:
    raise SystemExit("ERROR: Isolated HTTPS proxy not ready")
PY
# Ensure Vitals/Labs/COA tests actually run against a reverse proxy which
# rewrites upstream Host; otherwise the regression would be a false pass.
grep -qx 'QA_WRITE_PROXY_HOST_REWRITE=ENABLED' "$TLS_LOG" || {
  echo "ERROR: isolated reverse-proxy Host-rewrite fixture was not enabled"
  exit 2
}
echo "ISOLATED_PROXY_HOST_REWRITE=VERIFIED"

echo "=== DISPOSABLE INVENTORY FOR LIVE SORT/SEARCH QA ==="
# Only mutate the private candidate database created above. Never touch the
# installed Tracker database or user files.
env -i HOME=/root PATH=/usr/local/bin:/usr/bin:/bin \
  PYTHONPATH="$SOURCE" TRACKER_DATA_DIR="$DATA" TRACKER_INSTANCE=DEV \
  PYTHONDONTWRITEBYTECODE=1 "$PY" -B - <<'PY'
from app.db import SessionLocal
from app.models import Compound, Vial, PreparationEvent

with SessionLocal() as db:
    for compound_name in ("QA Alpha 511", "QA Zeta 511"):
        compound = Compound(name=compound_name, category="peptide")
        db.add(compound)
        db.flush()
        vial = Vial(
            compound_id=compound.id,
            label=compound_name + " vial",
            status="in_use",
            content_value=100,
            content_unit="mg",
        )
        db.add(vial)
        db.flush()
        db.add(PreparationEvent(
            vial_id=vial.id, kind="filtering",
            notes="QA disposable preparation 576 " + compound_name,
        ))
    db.commit()
print("DISPOSABLE_INVENTORY_FIXTURES=2")
print("DISPOSABLE_PREPARATION_FIXTURES=2")
PY

# Release 628: operator standardizes pytest-xdist at 16 workers and
# systemd release worker at a 16 GiB memory ceiling; maintain separate
# isolated browser modules where evidence sequencing requires it.
# Preserve parallel execution without overlapping
# conflicting mutations against the same disposable SQLite database.
run_isolated_browser_module() {
    local module="$1"
    local strict="$2"
    local logfile="$3"
    local rc

    local -a envvars=(
        HOME=/root
        PATH=/usr/local/bin:/usr/bin:/bin
        PYTHONPATH="$SOURCE"
        TRACKER_DATA_DIR="$DATA"
        TRACKER_TEST_URL="$URL"
        TRACKER_TEST_HTTPS_URL="$HTTPS_URL"
        TRACKER_TEST_ISOLATED=1
        TRACKER_BROWSER_QA_DATA_DIR="$DATA"
        PYTHONDONTWRITEBYTECODE=1
        PYTHONUNBUFFERED=1
    )

    if [[ "$strict" == 1 ]]; then
        envvars+=(TRACKER_TEST_STRICT_CSRF=1)
    fi

    echo
    echo "=== BROWSER MODULE: $module (strict=$strict) ==="
    # Release 628: fixed 16-worker qualification for full and targeted modes.
    # Do not silently revert to 4 or 1 workers. The enclosing release
    # service keeps a 16 GiB memory ceiling.
    local -a pytest_command=(
        "$PY" -B -m pytest -n 16 --dist=loadfile
        -q --tb=short "$module"
    )
    echo "WORKERS=16"
    echo "MODULE_LOG=$logfile"

    set +e
    env -i "${envvars[@]}" "${pytest_command[@]}" \
        2>&1 | tee "$logfile"

    rc=${PIPESTATUS[0]}
    set -e

    # Release 716: publish only fixed test-step names, never browser output,
    # private data, or raw exception messages, when the isolated UI test fails.
    if [[ "${module##*/}" == test_workout_active716.py ]]; then
        local stage_file="$DATA/workout716-stages.txt"
        if [[ -f "$stage_file" && ! -L "$stage_file" ]]; then
            local stage
            while IFS= read -r stage; do
                if [[ "$stage" =~ ^TARGETED_716_(HTTP|HTTPS)_(MACHINE_ONE|CATALOG|ROUTINE_CREATED|ROUTINE_READY|STARTED|LINKS|PANEL|SELECTED|POSTED|HEADING|PROGRESS|WIDTH|EXISTING|NEW|FINISHED|SERVER_OK|SERVER_FAIL|PAGE_GYM|PAGE_OTHER|HEADING_SAME|HEADING_FIRST|HEADING_OTHER|HEADING_MISSING|ID_MATCH|ID_OTHER|HEADING_ROW|HEADING_NOT_ROW|HEADING_QA|HEADING_NOT_QA|LABEL_SECOND|LABEL_OTHER)=PASSED$ ]]; then
                    echo "$stage"
                fi
            done < "$stage_file"
        fi
    fi
    # Release 719: only fixed safe mobile workflow checkpoints are emitted.
    if [[ "${module##*/}" == test_workout_manage719.py ]]; then
        local stage_file719="$DATA/workout719-stages.txt"
        if [[ -f "$stage_file719" && ! -L "$stage_file719" ]]; then
            local milestone719
            while IFS= read -r milestone719; do
                if [[ "$milestone719" =~ ^TARGETED_719_(HTTP|HTTPS)_(HOME_LOADED|HOME_EXPANDED|STARTED|DELETE_LINK|ACTIVE_FORM|ACTIVE_POST|ACTIVE_RETURN|MACHINE|RESTARTED|LOGGED|FINISHED|FINISHED_FORM|FINISHED_POST|END)=PASSED$ ]]; then
                    echo "$milestone719"
                fi
            done < "$stage_file719"
        fi
    fi
    echo "MODULE_EXIT=$rc"
    return "$rc"
}

if [[ "$MODE" == full ]]; then
# Release 705: register 15 omitted modules in existing disposable
# 16-worker standard gate. Parity 699/700 skip without pinned preview roots.
echo "=== OFFLINE FOOD AND LABS BROWSER TESTS + LIVE NAVIGATION ==="
set +e
env -i HOME=/root PATH=/usr/local/bin:/usr/bin:/bin \
  PYTHONPATH="$SOURCE" TRACKER_DATA_DIR="$DATA" \
  TRACKER_TEST_URL="$URL" TRACKER_TEST_HTTPS_URL="$HTTPS_URL" \
  TRACKER_TEST_ISOLATED=1 TRACKER_BROWSER_QA_DATA_DIR="$DATA" \
  PYTHONDONTWRITEBYTECODE=1 \
  "$PY" -B -m pytest -n 16 --dist=loadfile -q --tb=short \
    tests/browser/test_food_search_ui.py \
    tests/browser/test_inventory_alert_csv_review.py \
    tests/browser/test_lab_compare_review.py \
    tests/browser/test_labs_overview.py \
    tests/browser/test_purchase_history_review.py \
    tests/browser/test_supply_consumption_review.py \
    tests/test_bulk_vial_browser.py \
    tests/test_bulk_vial_guided_browser.py \
    tests/test_bulk_delete_browser.py \
    tests/test_purchase_vial_browser.py \
    tests/test_stage33_browser_sorting.py \
    tests/test_health_timeline_dates_browser.py \
    tests/test_vitals_csv_browser.py \
    tests/browser/test_food_labs_live499.py \
    tests/browser/test_food_labs_mutations500.py \
    tests/browser/test_vitals_proxy_host522.py \
    tests/browser/test_navigation.py \
    tests/browser/test_form_overlap586.py \
    tests/browser/test_regimen_catalog638_ui.py \
    tests/browser/test_regimen_facts639_ui.py \
    tests/browser/test_pk_smoke_281.py \
    tests/browser/test_stage33_live_sorting.py \
    tests/browser/test_consolidated_forms704.py \
    tests/browser/test_css_parity699.py \
    tests/browser/test_css_parity700.py \
    tests/browser/test_daily_flow695.py \
    tests/browser/test_integrated_flow696.py \
    tests/browser/test_mobile_edit_actions703.py \
    tests/browser/test_mobile_quick_actions701.py \
    tests/browser/test_saved_food_mobile_actions702.py \
    tests/browser/test_workout_calendar664.py \
    tests/browser/test_workout_dashboard661.py \
    tests/browser/test_workout_plan665.py \
    tests/browser/test_workout_program667.py \
    tests/browser/test_workout_targets666.py \
    tests/browser/test_workouts_quick659.py \
    tests/browser/test_workouts_quick662.py 2>&1 | tee "$TEST_LOG"
BROWSER_EXIT=${PIPESTATUS[0]}
set -e
echo "BROWSER_PYTEST_EXIT=$BROWSER_EXIT"

(( BROWSER_EXIT == 0 )) || exit "$BROWSER_EXIT"
echo "=== REGULAR BROWSER SUITE PASSED ==="

run_isolated_browser_module \
    tests/browser/test_labs_native_https501.py \
    0 "$ROOT/labs501-browser.log"
fi

# Release 521: a second browser gate runs the SAME isolated candidate
# with global strict CSRF enabled. Existing report-only browser tests still
# run above. Never restart, reconfigure, or test against the installed app.
echo "=== STRICT CSRF CHROMIUM GATE — DISPOSABLE CANDIDATE ONLY ==="
echo "STRICT_CSRF_MODE=1"
kill "$SERVER_PID" 2>/dev/null || true
wait "$SERVER_PID" 2>/dev/null || true
SERVER_PID=""
STRICT_SERVER_LOG="$ROOT/strict-server.log"
STRICT_TEST_LOG="$ROOT/strict-browser.log"

env -i HOME=/root PATH=/usr/local/bin:/usr/bin:/bin \
  PYTHONPATH="$SOURCE" TRACKER_DATA_DIR="$DATA" TRACKER_INSTANCE=DEV \
  TRACKER_CSRF_ENFORCE=1 PYTHONDONTWRITEBYTECODE=1 \
  "$PY" -B -m uvicorn app.main:app --host 127.0.0.1 \
    --port "$PORT" --app-dir "$SOURCE" >"$STRICT_SERVER_LOG" 2>&1 &
SERVER_PID=$!

"$PY" - "$URL" "$SERVER_PID" <<'PY'
import os
import sys
import time
import urllib.error
import urllib.request

url, pid = sys.argv[1], int(sys.argv[2])
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
for _ in range(60):
    try:
        os.kill(pid, 0)
        with opener.open(url + "/healthz", timeout=2) as response:
            if response.status != 200 or b'"ok":true' not in response.read().replace(b' ', b''):
                raise RuntimeError("Strict candidate health unavailable")
        # Prove strict mode is active before browser testing. A JSON write
        # with neither a cookie nor a header must be denied by middleware.
        request = urllib.request.Request(
            url + "/pk/compounds",
            data=b'{}',
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            opener.open(request, timeout=3)
        except urllib.error.HTTPError as error:
            if error.code == 403 and b"CSRF token required" in error.read():
                print("ISOLATED_STRICT_CSRF_READY=YES")
                break
        raise RuntimeError("Strict-CSRF fail-closed probe did not return 403")
    except (OSError, urllib.error.URLError, RuntimeError):
        time.sleep(0.5)
else:
    raise SystemExit("ERROR: strict candidate did not become ready or enforce CSRF")
PY

# Release 705: narrow HTTP + HTTPS strict-Vials / Quick Entry browser
# preflight. Two real Chromium cases; no writes to installed DEV/PROD and
# NOT a substitute for the full standard + strict suites.
if [[ "$MODE" == targeted && "$TARGETED_MODULE" == quick603 ]]; then
  echo "TARGETED_QUICK603_SCOPE=HTTP_HTTPS_STRICT_ONLY_NOT_FULL_QA"
  env -i HOME=/root PATH=/usr/local/bin:/usr/bin:/bin \
    PYTHONPATH="$SOURCE" TRACKER_DATA_DIR="$DATA" \
    TRACKER_TEST_URL="$URL" TRACKER_TEST_HTTPS_URL="$HTTPS_URL" \
    TRACKER_TEST_ISOLATED=1 TRACKER_TEST_STRICT_CSRF=1 \
    TRACKER_BROWSER_QA_DATA_DIR="$DATA" PYTHONDONTWRITEBYTECODE=1 \
    "$PY" -B -m pytest -q --tb=short --maxfail=1 \
    "tests/browser/test_strict_"\
"csrf521.py::test_603_vials_navigation_and_daily_action_filter"
  echo "TARGETED_QUICK603_HTTP_HTTPS=PASSED"
  exit 0
fi

# Release 705: targeted signed create/edit/delete plus negative probes for
# the complete Release 580 module in disposable strict HTTP and HTTPS.
# A focused pass never earns the full browser qualification marker.
if [[ "$MODE" == targeted && "$TARGETED_MODULE" == workflows580 ]]; then
  echo "TARGETED_WORKFLOWS580_SCOPE=HTTP_HTTPS_FULL_MODULE_NOT_FULL_QA"
  run_isolated_browser_module \
      tests/browser/"test_csrf_workflows580.py" \
      1 "$ROOT/targeted-workflows580.log"
  "$PY" "$SOURCE/scripts/tracker_csrf_runtime_report580.py" \
      --directory "$ROOT/csrf-runtime580"
  echo "TARGETED_WORKFLOWS580_HTTP_HTTPS=PASSED_NOT_FULL_QA"
  exit 0
fi

# Release 635: exact failing Notes title lifecycle only (HTTP + HTTPS).
# This preflight is NOT full browser qualification or a DEV approval receipt.
if [[ "$MODE" == targeted && "$TARGETED_MODULE" == note-title575 ]]; then
  echo "TARGETED_NOTES_575_SCOPE=HTTP_AND_HTTPS_ONLY"
  env -i HOME=/root PATH=/usr/local/bin:/usr/bin:/bin \
    PYTHONPATH="$SOURCE" TRACKER_DATA_DIR="$DATA" \
    TRACKER_TEST_URL="$URL" TRACKER_TEST_HTTPS_URL="$HTTPS_URL" \
    TRACKER_TEST_ISOLATED=1 TRACKER_TEST_STRICT_CSRF=1 \
    TRACKER_BROWSER_QA_DATA_DIR="$DATA" PYTHONDONTWRITEBYTECODE=1 \
    "$PY" -B -m pytest -q --tb=short --maxfail=1 \
    "tests/browser/test_strict_"\
"csrf521.py::test_575_create_and_edit_notes_with_rendered_dynamic_action"
  echo "TARGETED_NOTES_575=PASSED"
  exit 0
fi

if [[ "$MODE" == full ]]; then
# The HTTPS proxy continues to forward to the same loopback-only port.
# Run real native browser forms/uploads, HTMX, fetch, and previously qualified
# Labs/Food mutation workflows under strict mode. All data is disposable.
set +e
env -i HOME=/root PATH=/usr/local/bin:/usr/bin:/bin \
  PYTHONPATH="$SOURCE" TRACKER_DATA_DIR="$DATA" \
  TRACKER_TEST_URL="$URL" TRACKER_TEST_HTTPS_URL="$HTTPS_URL" \
  TRACKER_TEST_ISOLATED=1 TRACKER_TEST_STRICT_CSRF=1 \
  TRACKER_BROWSER_QA_DATA_DIR="$DATA" PYTHONDONTWRITEBYTECODE=1 \
  "$PY" -B -m pytest -n 16 --dist=loadfile -q --tb=short \
    tests/browser/test_strict_csrf521.py \
    2>&1 | tee "$STRICT_TEST_LOG"
STRICT_EXIT=${PIPESTATUS[0]}
set -e
echo "STRICT_BROWSER_PYTEST_EXIT=$STRICT_EXIT"
if (( STRICT_EXIT != 0 )); then
  echo "STRICT_BROWSER_TEST_LOG=$STRICT_TEST_LOG"
  echo "=== STRICT BROWSER FAILURE SUMMARY ==="
  grep -E '^(FAILED |ERROR |E   |[0-9]+ failed|[0-9]+ error)' "$STRICT_TEST_LOG" | tail -n 35 || true
  tail -n 20 "$STRICT_SERVER_LOG" || true
  exit "$STRICT_EXIT"
fi

echo "=== STRICT CSRF CORE TESTS PASSED ==="

echo "=== STRICT CSRF UNQUALIFIED WORKSTREAM NEGATIVE PROBES ==="
run_isolated_browser_module \
    tests/browser/test_csrf_gap627.py \
    1 "$ROOT/strict-gap627.log"
echo "STRICT_CSRF_627_GAP_NEGATIVE_PROBES=PASSED"

echo "=== STRICT CSRF SIGNED NATIVE CREATE LIFECYCLES ==="
run_isolated_browser_module \
    tests/browser/test_csrf_signed_lifecycles627.py \
    1 "$ROOT/strict-signed-lifecycles627.log"
echo "STRICT_CSRF_627_SIGNED_LIFECYCLES=PASSED"

echo "=== STRICT CSRF PURCHASE CHILD LIFECYCLES ==="
run_isolated_browser_module \
    tests/browser/test_csrf_purchase_children627.py \
    1 "$ROOT/strict-purchase-children627.log"
echo "STRICT_CSRF_627_PURCHASE_CHILDREN=PASSED"

echo "=== STRICT CSRF COA MULTIPART LIFECYCLES ==="
run_isolated_browser_module \
    tests/browser/test_csrf_coa_lifecycle627.py \
    1 "$ROOT/strict-coa-lifecycle627.log"
echo "STRICT_CSRF_627_COA_LIFECYCLE=PASSED"

# Release 715: real new/edit/vial COA Untested default with signed HTTP+HTTPS.
run_isolated_browser_module \
    tests/browser/test_coa_untested715.py \
    1 "$ROOT/strict-coa-untested715.log"
echo "STRICT_715_COA_UNTESTED=PASSED"

# Release 716: real signed, mobile workout machine editing on HTTP and HTTPS.
run_isolated_browser_module \
    tests/browser/test_workout_active716.py \
    1 "$ROOT/strict-workout-active716.log"
echo "STRICT_716_ACTIVE_WORKOUT=PASSED"

# Release 717: completed-session edit and confirmed removal, signed HTTP/HTTPS.
run_isolated_browser_module \
    tests/browser/test_workout_completed717.py \
    1 "$ROOT/strict-workout-completed717.log"
echo "STRICT_717_COMPLETED_WORKOUT=PASSED"

# Release 718: completed-session machine correction signed in both protocols.
run_isolated_browser_module \
    tests/browser/test_workout_machine718.py \
    1 "$ROOT/strict-workout-machine718.log"
echo "STRICT_718_MACHINE_CORRECTION=PASSED"

# Release 719: signed empty/completed workout delete and collapsed dashboard.
run_isolated_browser_module \
    tests/browser/test_workout_manage719.py \
    1 "$ROOT/strict-workout-manage719.log"
echo "STRICT_719_WORKOUT_MANAGEMENT=PASSED"

echo "=== STRICT CSRF REMAINING PROTOCOL SIGNED LIFECYCLES ==="
run_isolated_browser_module \
    tests/browser/test_csrf_protocol_remaining627.py \
    1 "$ROOT/strict-protocol-remaining627.log"
echo "STRICT_CSRF_627_PROTOCOL_REMAINING=PASSED"

echo "=== STRICT CSRF SIGNED READ-ONLY BLEND PREVIEWS ==="
run_isolated_browser_module \
    tests/browser/test_csrf_blend_previews627.py \
    1 "$ROOT/strict-blend-previews627.log"
echo "STRICT_CSRF_627_BLEND_PREVIEWS=PASSED"

# Release 710: real mixed-compound prepared vial dose through /doses.
run_isolated_browser_module \
    tests/browser/test_blend_unified_dose710.py \
    1 "$ROOT/strict-blend-unified710.log"
echo "STRICT_710_UNIFIED_BLEND_VIAL_DOSE=PASSED"

# Release 711: correct and delete an existing physical blend draw.
run_isolated_browser_module \
    tests/browser/test_blend_corrections711.py \
    1 "$ROOT/strict-blend-corrections711.log"
echo "STRICT_711_BLEND_CORRECTION_DELETE=PASSED"

# Release 712: U-100 syringe units via one standard dose form.
run_isolated_browser_module \
    tests/browser/test_u100_withdraw712.py \
    1 "$ROOT/strict-u100-withdraw712.log"
echo "STRICT_712_U100_WITHDRAW=PASSED"

# Release 713: global HH:MM time controls across current Tracker modules.
run_isolated_browser_module \
    tests/browser/test_global_time24_713.py \
    1 "$ROOT/strict-global-time24-713.log"
echo "STRICT_713_GLOBAL_TIME24=PASSED"

run_isolated_browser_module \
    tests/browser/test_food_labs_mutations500.py \
    1 "$ROOT/strict-labs500.log"

run_isolated_browser_module \
    tests/browser/test_labs_native_https501.py \
    1 "$ROOT/strict-labs501.log"

# Release 579: pair executable browser write + unsigned replay tests
# with a strict, closed-schema private evidence receipt. A missing
# browser witness or unexpected response blocks the entire DEV gate.
run_isolated_browser_module \
    tests/browser/test_csrf_runtime579.py \
    1 "$ROOT/strict-runtime579.log"

"$PY" "$SOURCE/scripts/tracker_csrf_runtime_report579.py" \
    --directory "$ROOT/csrf-runtime579"

# Release 580: the distinct compound, vitals and Notes lifecycle gate
# exercises signed create/edit/delete with negative forged replays.
# Neither a failed browser scenario nor incomplete receipt is allowed
# to produce the strict browser success marker.
run_isolated_browser_module \
    tests/browser/test_csrf_workflows580.py \
    1 "$ROOT/strict-workflows580.log"

"$PY" "$SOURCE/scripts/tracker_csrf_runtime_report580.py" \
    --directory "$ROOT/csrf-runtime580"

# Release 581: qualified synthetic-vial native update and genuine HTMX
# dose-preview writes; keep forged-only cases explicitly separate.
run_isolated_browser_module \
    tests/browser/test_csrf_inventory581.py \
    1 "$ROOT/strict-inventory-dose581.log"

"$PY" "$SOURCE/scripts/tracker_csrf_runtime_report581.py" \
    --directory "$ROOT/csrf-runtime581"

# Release 582: signed dose create/correct/delete using the real browser UI,
# with paired unsigned denial and a private, fail-closed witness ledger.
run_isolated_browser_module \
    tests/browser/test_csrf_dose_lifecycle582.py \
    1 "$ROOT/strict-dose-lifecycle582.log"

"$PY" "$SOURCE/scripts/tracker_csrf_runtime_report582.py" \
    --directory "$ROOT/csrf-runtime582"
fi

if [[ "$MODE" == targeted ]]; then
  echo "TARGETED_STRICT_PREFLIGHT=ACTIVE"
  echo "TARGETED_STRICT_MODULE=$TARGETED_MODULE"
fi
# Release 710: actual HTTP and HTTPS strict-CSRF /doses browser write.
# This targeted smoke does not certify the full release or enable global CSRF.
if [[ "$MODE" == targeted && "$TARGETED_MODULE" == blend-vial710 ]]; then
  run_isolated_browser_module \
      tests/browser/test_blend_unified_dose710.py \
      1 "$ROOT/targeted-blend-unified710.log"
  echo "TARGETED_710_UNIFIED_BLEND_VIAL_DOSE=PASSED"
  echo "TARGETED_710_SCOPE=ONE_REAL_PHYSICAL_BLEND_WRITE_NOT_FULL_RELEASE"
  exit 0
fi

# Release 711: signed native edit and confirmed delete over HTTP and HTTPS.
# A targeted witness is not a full CSRF rollout qualification.
if [[ "$MODE" == targeted && "$TARGETED_MODULE" == blend-correction711 ]]; then
  run_isolated_browser_module \
      tests/browser/test_blend_corrections711.py \
      1 "$ROOT/targeted-blend-corrections711.log"
  echo "TARGETED_711_BLEND_CORRECTION_DELETE=PASSED"
  echo "TARGETED_711_SCOPE=REAL_CORRECTION_AND_DELETE_NOT_FULL_RELEASE"
  exit 0
fi

# Release 712: one scoped real-UI browser witness for vial and prepared blend.
if [[ "$MODE" == targeted && "$TARGETED_MODULE" == u100-withdraw712 ]]; then
  run_isolated_browser_module \
      tests/browser/test_u100_withdraw712.py \
      1 "$ROOT/targeted-u100-withdraw712.log"
  echo "TARGETED_712_U100_WITHDRAW=PASSED"
  echo "TARGETED_712_SCOPE=VIAL_AND_BLEND_U100_NOT_FULL_RELEASE"
  exit 0
fi

# Release 715: one scoped strict HTTP/HTTPS COA result-status UI witness.
if [[ "$MODE" == targeted && "$TARGETED_MODULE" == coa-untested715 ]]; then
  run_isolated_browser_module \
      tests/browser/test_coa_untested715.py \
      1 "$ROOT/targeted-coa-untested715.log"
  echo "TARGETED_715_COA_UNTESTED=PASSED"
  echo "TARGETED_715_SCOPE=COA_CREATE_EDIT_VIAL_NOT_FULL_RELEASE"
  exit 0
fi

# Release 716: one scoped strict HTTP/HTTPS in-workout machine edit witness.
if [[ "$MODE" == targeted && "$TARGETED_MODULE" == workout-active716 ]]; then
  run_isolated_browser_module \
      tests/browser/test_workout_active716.py \
      1 "$ROOT/targeted-workout-active716.log"
  echo "TARGETED_716_ACTIVE_WORKOUT=PASSED"
  echo "TARGETED_716_SCOPE=ACTIVE_MACHINE_ADD_AND_NEW_NOT_FULL_RELEASE"
  exit 0
fi

# Release 717: isolated browser check for editing a completed workout.
if [[ "$MODE" == targeted && "$TARGETED_MODULE" == workout-completed717 ]]; then
  run_isolated_browser_module \
      tests/browser/test_workout_completed717.py \
      1 "$ROOT/targeted-workout-completed717.log"
  echo "TARGETED_717_COMPLETED_WORKOUT=PASSED"
  echo "TARGETED_717_SCOPE=HISTORICAL_SET_REMOVAL_NOT_FULL_RELEASE"
  exit 0
fi

# Release 718: isolated signed bulk/single completed-set machine correction.
if [[ "$MODE" == targeted && "$TARGETED_MODULE" == workout-machine718 ]]; then
  run_isolated_browser_module \
      tests/browser/test_workout_machine718.py \
      1 "$ROOT/targeted-workout-machine718.log"
  echo "TARGETED_718_MACHINE_CORRECTION=PASSED"
  echo "TARGETED_718_SCOPE=COMPLETED_MACHINE_REASSIGNMENT_NOT_FULL_RELEASE"
  exit 0
fi

# Release 719: isolated signed completed and active workout deletion.
if [[ "$MODE" == targeted && "$TARGETED_MODULE" == workout-manage719 ]]; then
  run_isolated_browser_module \
      tests/browser/test_workout_manage719.py \
      1 "$ROOT/targeted-workout-manage719.log"
  echo "TARGETED_719_WORKOUT_MANAGEMENT=PASSED"
  echo "TARGETED_719_SCOPE=SIGNED_WORKOUT_DELETE_AND_COLLAPSED_DASHBOARD_NOT_FULL_RELEASE"
  exit 0
fi

# Release 713: real cross-module browser witness of 24-hour entry controls.
if [[ "$MODE" == targeted && "$TARGETED_MODULE" == global-time24-713 ]]; then
  run_isolated_browser_module \
      tests/browser/test_global_time24_713.py \
      1 "$ROOT/targeted-global-time24-713.log"
  echo "TARGETED_713_GLOBAL_TIME24=PASSED"
  echo "TARGETED_713_SCOPE=ALL_TIME_FIELDS_NOT_FULL_RELEASE"
  exit 0
fi

# Release 627: one disposable targeted smoke for only the new consolidated
# browser modules. Not a full QA run and never a promotion receipt.
if [[ "$MODE" == targeted && "$TARGETED_MODULE" == csrf-batch627 ]]; then
  run_isolated_browser_module \
      tests/browser/test_csrf_gap627.py \
      1 "$ROOT/batch627-negative.log"
  run_isolated_browser_module \
      tests/browser/test_csrf_signed_lifecycles627.py \
      1 "$ROOT/batch627-positive.log"
  run_isolated_browser_module \
      tests/browser/test_csrf_purchase_children627.py \
      1 "$ROOT/batch627-purchases.log"
  run_isolated_browser_module \
      tests/browser/test_csrf_coa_lifecycle627.py \
      1 "$ROOT/batch627-coa.log"
  echo "TARGETED_CSRF_BATCH627=PASSED"
  echo "TARGETED_CSRF_BATCH627_SCOPE=NEW_BROWSER_ONLY_NOT_FULL_QUALIFICATION"
  exit 0
fi

# Release 627: only rerun the three positive modules after correcting their
# form encoding. Previously qualified negative probes need not be repeated
# in a debugging smoke. This remains NOT full qualification.
if [[ "$MODE" == targeted && "$TARGETED_MODULE" == csrf-positive627 ]]; then
  run_isolated_browser_module \
      tests/browser/test_csrf_signed_lifecycles627.py \
      1 "$ROOT/positive627-native.log"
  run_isolated_browser_module \
      tests/browser/test_csrf_purchase_children627.py \
      1 "$ROOT/positive627-purchase.log"
  run_isolated_browser_module \
      tests/browser/test_csrf_coa_lifecycle627.py \
      1 "$ROOT/positive627-coa.log"
  run_isolated_browser_module \
      tests/browser/test_csrf_protocol_remaining627.py \
      1 "$ROOT/positive627-protocol.log"
  run_isolated_browser_module \
      tests/browser/test_csrf_blend_previews627.py \
      1 "$ROOT/positive627-blend-previews.log"
  echo "TARGETED_CSRF_POSITIVE627=PASSED"
  echo "TARGETED_CSRF_POSITIVE627_SCOPE=NEW_POSITIVE_BROWSER_ONLY"
  exit 0
fi

# Release 627: only the eight newly added protocol and preview routes.
# Keep the already-passed 19-route positive modules and negative suite out
# of this cheap diagnostic; a later full release qualification still runs all.
if [[ "$MODE" == targeted && "$TARGETED_MODULE" == csrf-new627 ]]; then
  run_isolated_browser_module \
      tests/browser/test_csrf_protocol_remaining627.py \
      1 "$ROOT/new627-protocol.log"
  run_isolated_browser_module \
      tests/browser/test_csrf_blend_previews627.py \
      1 "$ROOT/new627-blend-previews.log"
  echo "TARGETED_CSRF_NEW627=PASSED"
  echo "TARGETED_CSRF_NEW627_SCOPE=EIGHT_NEW_ROUTES_NOT_FULL_QA"
  exit 0
fi

# Release 586: targeted layout module seeds its own synthetic dose.
# This path is never a substitute for the full QA browser gate.
if [[ "$MODE" == targeted && "${TARGETED_MODULE##*/}" == test_form_overlap586.py ]]; then
  run_isolated_browser_module "$TARGETED_MODULE" 1 "$ROOT/targeted-layout586.log"
  echo "TARGETED_LAYOUT_PREFLIGHT=PASSED"
  echo "TARGETED_LAYOUT_SCOPE=RELEASE_586_ONLY_NOT_FULL_QUALIFICATION"
  exit 0
fi

# Release 589: one explicit fail-closed batch replaces duplicate server startup
# and backend tests for the two established strict browser modules.
# This is targeted evidence only; never claim full browser qualification.
if [[ "$MODE" == targeted && "$TARGETED_MODULE" == csrf-batch589 ]]; then
  run_isolated_browser_module \
      tests/browser/test_csrf_bulk587.py \
      1 "$ROOT/batch589-bulk.log"
  "$PY" "$SOURCE/scripts/tracker_csrf_runtime_report587.py" \
      --directory "$ROOT/csrf-runtime587"
  run_isolated_browser_module \
      tests/browser/test_csrf_multipart588.py \
      1 "$ROOT/batch589-multipart.log"
  echo "TARGETED_CSRF_BATCH589=PASSED"
  echo "TARGETED_CSRF_BATCH589_SCOPE=BULK587_MULTIPART588_ONLY_NOT_FULL_QUALIFICATION"
  exit 0
fi

# Combined Release 587–588: isolate bulk inventory browser writes
# and unsigned denials without touching installed data. This is a
# separate security witness, not global strict-CSRF clearance.
if [[ "$MODE" == targeted && "${TARGETED_MODULE##*/}" == test_csrf_bulk587.py ]]; then
  run_isolated_browser_module "$TARGETED_MODULE" 1 "$ROOT/targeted-bulk587.log"
  echo "TARGETED_BULK587_PREFLIGHT=PASSED"
  echo "TARGETED_BULK587_SCOPE=SYNTHETIC_BROWSER_FETCH_NOT_GLOBAL_CLEARANCE"
  exit 0
fi

if [[ "$MODE" == full ]]; then
  run_isolated_browser_module \
      tests/browser/test_csrf_multipart588.py \
      1 "$ROOT/strict-multipart588.log"
  echo "CSRF_588_NATIVE_MULTIPART_HTTP_HTTPS=PASSED"
  run_isolated_browser_module \
      tests/browser/test_csrf_bulk587.py \
      1 "$ROOT/strict-bulk587.log"
  "$PY" "$SOURCE/scripts/tracker_csrf_runtime_report587.py" \
      --directory "$ROOT/csrf-runtime587"
fi

if [[ "$MODE" == targeted && "${TARGETED_MODULE##*/}" == test_csrf_multipart588.py ]]; then
  run_isolated_browser_module "$TARGETED_MODULE" 1 "$ROOT/targeted-multipart588.log"
  echo "TARGETED_MULTIPART588_PREFLIGHT=PASSED"
  echo "TARGETED_MULTIPART588_SCOPE=NATIVE_COA_UPLOAD_ONLY_NOT_GLOBAL_CLEARANCE"
  exit 0
fi

# Release 583: inject synthetic supplies only after previous gates finish.
# Never touch installed DEV/PROD data. Strict mode remains confined to
# the disposable QA localhost backend.
env -i HOME=/root PATH=/usr/local/bin:/usr/bin:/bin \
  PYTHONPATH="$SOURCE" TRACKER_DATA_DIR="$DATA" TRACKER_INSTANCE=DEV \
  TRACKER_TEST_ISOLATED=1 TRACKER_TEST_STRICT_CSRF=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  "$PY" -B "$SOURCE/scripts/tracker_csrf_fixture583.py" seed

run_isolated_browser_module \
    tests/browser/test_csrf_preparations583.py \
    1 "$ROOT/strict-preparations583.log"

"$PY" "$SOURCE/scripts/tracker_csrf_runtime_report583.py" \
    --directory "$ROOT/csrf-runtime583"

env -i HOME=/root PATH=/usr/local/bin:/usr/bin:/bin \
  PYTHONPATH="$SOURCE" TRACKER_DATA_DIR="$DATA" TRACKER_INSTANCE=DEV \
  TRACKER_TEST_ISOLATED=1 TRACKER_TEST_STRICT_CSRF=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  "$PY" -B "$SOURCE/scripts/tracker_csrf_fixture583.py" verify

if [[ "$MODE" == full ]]; then
  echo "ISOLATED_STRICT_CSRF_BROWSER=PASSED"
else
  echo "TARGETED_STRICT_PREFLIGHT=PASSED"
  echo "TARGETED_STRICT_SCOPE=RELEASE_583_ONLY_NOT_FULL_QUALIFICATION"
fi
