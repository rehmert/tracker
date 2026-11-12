#!/usr/bin/env bash
# Release 498: isolated, offline browser qualification for a candidate worktree.
# Only localhost; never reads /etc/tracker.env or the installed Tracker database.
set -Eeuo pipefail
umask 077

[[ $# == 2 ]] || { echo "Usage: tracker-browser-qualify.sh SOURCE PYTHON" >&2; exit 2; }
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

# Release 524: preserve parallel execution without overlapping
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
    echo "WORKERS=16"
    echo "MODULE_LOG=$logfile"

    set +e
    env -i "${envvars[@]}" \
        "$PY" -B -m pytest \
        -n 16 --dist=loadfile \
        -q --tb=short "$module" \
        2>&1 | tee "$logfile"

    rc=${PIPESTATUS[0]}
    set -e

    echo "MODULE_EXIT=$rc"
    return "$rc"
}

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
    tests/browser/test_pk_smoke_281.py \
    tests/browser/test_stage33_live_sorting.py 2>&1 | tee "$TEST_LOG"
BROWSER_EXIT=${PIPESTATUS[0]}
set -e
echo "BROWSER_PYTEST_EXIT=$BROWSER_EXIT"

(( BROWSER_EXIT == 0 )) || exit "$BROWSER_EXIT"
echo "=== REGULAR BROWSER SUITE PASSED ==="

run_isolated_browser_module \
    tests/browser/test_labs_native_https501.py \
    0 "$ROOT/labs501-browser.log"


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

run_isolated_browser_module \
    tests/browser/test_food_labs_mutations500.py \
    1 "$ROOT/strict-labs500.log"

run_isolated_browser_module \
    tests/browser/test_labs_native_https501.py \
    1 "$ROOT/strict-labs501.log"

echo "ISOLATED_STRICT_CSRF_BROWSER=PASSED"
