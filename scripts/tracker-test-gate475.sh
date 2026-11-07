#!/usr/bin/env bash
set -euo pipefail

APP=/opt/tracker
PY="$APP/.venv/bin/python"

[[ -x "$PY" ]] || {
    echo "ERROR: Tracker virtualenv missing"
    exit 1
}

cd "$APP"

MODE="${1:-}"

case "$MODE" in
    non-browser)
        echo "=== COMPLETE NON-BROWSER REGRESSION SUITE ==="
        echo "Browser tests excluded: require live"
        echo "authenticated browser fixture."

        "$PY" -m pytest \
            -q \
            --ignore=tests/browser \
            --disable-warnings \
            --tb=short

        echo "=== NON-BROWSER REGRESSION SUCCESS ==="
        ;;

    multiuser)
        echo "=== MULTI-USER SECURITY ACCEPTANCE ==="

        "$PY" -m pytest -q \
            tests/test_multiuser_launch475.py \
            tests/test_multiuser_audit474.py \
            tests/test_unified_login473.py \
            tests/test_secondary_preview430.py \
            tests/test_secondary_files472.py \
            tests/test_secondary_attachments471.py \
            tests/test_secondary_food_inventory_orm470.py \
            tests/test_secondary_recent_orm469.py \
            tests/test_secondary_orm468.py \
            tests/test_secondary_request_db467.py \
            tests/test_secondary_cutover466.py \
            tests/test_secondary_account465.py \
            tests/test_secondary_workspace464.py \
            tests/test_secondary_integration440.py \
            tests/test_secondary_sessions441.py \
            tests/test_secondary_password451.py \
            tests/test_request_scope393.py \
            tests/test_scoped_db390.py \
            --disable-warnings \
            --tb=short

        echo "=== MULTI-USER SECURITY SUCCESS ==="
        ;;

    browser)
        echo "=== EXTERNAL BROWSER ACCEPTANCE ==="

        [[ -n "${TRACKER_TEST_URL:-}" ]] || {
            echo "ERROR: Set TRACKER_TEST_URL"
            echo "Browser tests require a separately"
            echo "prepared authenticated test server."
            exit 2
        }

        echo "TARGET=$TRACKER_TEST_URL"

        "$PY" -m pytest -q \
            tests/browser \
            --disable-warnings \
            --tb=short

        echo "=== BROWSER ACCEPTANCE SUCCESS ==="
        ;;

    *)
        echo "Usage: $0 non-browser|multiuser|browser" >&2
        exit 2
        ;;
esac
