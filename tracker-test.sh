#!/usr/bin/env bash
set -Eeuo pipefail

cd /opt/tracker

PYTHON="/opt/tracker/.venv/bin/python"
MODE="${1:-quick}"

BROWSER_TEST="tests/test_bulk_vial_browser.py"

run_timed() {
    local start=$SECONDS
    local result=0

    "$@" || result=$?

    echo
    echo "Elapsed: $((SECONDS - start)) seconds"
    return "$result"
}

case "$MODE" in

    quick)
        echo "=== TRACKER QUICK TESTS ==="

        "$PYTHON" -m compileall -q app

        run_timed "$PYTHON" -m pytest \
            -q \
            tests/test_bulk_vial_transactions.py \
            tests/test_bulk_vial_stage5.py \
            --tb=short
        ;;

    full)
        echo "=== TRACKER FULL REGRESSION ==="

        "$PYTHON" -m compileall -q app

        run_timed "$PYTHON" -m pytest \
            -q tests \
            --ignore="$BROWSER_TEST" \
            --ignore=tests/browser \
            --durations=10 \
            --tb=short
        ;;

    browser)
        echo "=== TRACKER BROWSER TESTS ==="

        run_timed "$PYTHON" -m pytest \
            -q "$BROWSER_TEST" \
            --tb=short
        ;;

    all)
        echo "=== TRACKER COMPLETE VALIDATION ==="

        "$PYTHON" -m compileall -q app

        run_timed "$PYTHON" -m pytest \
            -q tests \
            --ignore=tests/browser \
            --durations=10 \
            --tb=short
        ;;

    none)
        echo "=== TRACKER SYNTAX VALIDATION ONLY ==="

        "$PYTHON" -m compileall -q app
        echo "Pytest skipped by explicit request."
        ;;

    *)
        echo "Usage: $0 {quick|full|browser|all|none}"
        exit 2
        ;;

esac
