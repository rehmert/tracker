#!/usr/bin/env bash
set -Eeuo pipefail

cd /opt/tracker

PYTHON="/opt/tracker/.venv/bin/python"
MODE="${1:-quick}"

START=$SECONDS

load_browser_auth() {
    # Read credentials using Tracker's Python configuration.
    # Never evaluate .env as shell code.

    local credentials
    credentials="$(mktemp)"
    chmod 600 "$credentials"

    "$PYTHON" - "$credentials" <<'PY'
import sys
from pathlib import Path

from app import config

path = Path(sys.argv[1])

username = config.AUTH_USER
password = config.AUTH_PASS

if not username or not password:
    raise SystemExit(
        "Tracker authentication credentials are unavailable."
    )

with path.open("wb") as output:
    output.write(username.encode("utf-8"))
    output.write(b"\0")
    output.write(password.encode("utf-8"))
PY

    local username password

    IFS= read -r -d '' username < "$credentials" || true

    password="$(
        "$PYTHON" - "$credentials" <<'PY'
import sys
from pathlib import Path

data = Path(sys.argv[1]).read_bytes()
print(data.split(b"\0", 1)[1].decode("utf-8"), end="")
PY
    )"

    rm -f "$credentials"

    export TRACKER_TEST_USER="$username"
    export TRACKER_TEST_PASSWORD="$password"
}

syntax_check() {
    "$PYTHON" -m compileall -q app
}

run_quick() {
    echo "=== QUICK TESTS ==="

    syntax_check

    "$PYTHON" -m pytest \
        -q tests \
        -m "quick and not browser" \
        --ignore=tests/browser \
        --tb=short
}

run_full() {
    echo "=== FULL BACKEND TESTS ==="

    syntax_check

    "$PYTHON" -m pytest \
        -q tests \
        --ignore=tests/browser \
        --ignore=tests/test_bulk_vial_browser.py \
        --durations=10 \
        --tb=short
}

run_browser() {
    echo "=== ISOLATED BROWSER TESTS ==="

    "$PYTHON" -m pytest \
        -q tests/test_bulk_vial_browser.py \
        --tb=short
}

run_all() {
    echo "=== COMPLETE ISOLATED TESTS ==="

    syntax_check

    "$PYTHON" -m pytest \
        -q tests \
        --ignore=tests/browser \
        --durations=10 \
        --tb=short
}

run_live() {
    echo "=== AUTHENTICATED LIVE BROWSER TESTS ==="

    load_browser_auth

    "$PYTHON" -m pytest \
        -q tests/browser \
        --tb=short
}

case "$MODE" in
    quick)
        run_quick
        ;;
    full)
        run_full
        ;;
    browser)
        run_browser
        ;;
    all)
        run_all
        ;;
    live)
        run_live
        ;;
    release)
        echo "=== TRACKER RELEASE VALIDATION ==="

        run_all
        run_live
        ;;
    none)
        syntax_check
        ;;
    *)
        echo "Usage: $0 {quick|full|browser|all|live|release|none}"
        exit 2
        ;;
esac

echo
echo "Elapsed: $((SECONDS - START)) seconds"
