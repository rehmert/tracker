#!/usr/bin/env bash
set -Eeuo pipefail

cd /opt/tracker

PYTHON=".venv/bin/python"
MODE="${1:-quick}"

start=$SECONDS

case "$MODE" in

quick)
    echo "=== QUICK TESTS ==="

    "$PYTHON" -m compileall -q app

    "$PYTHON" -m pytest \
        -q tests \
        -m "quick and not browser" \
        --ignore=tests/browser \
        --tb=short
    ;;

full)
    echo "=== FULL BACKEND REGRESSION ==="

    "$PYTHON" -m compileall -q app

    "$PYTHON" -m pytest \
        -q tests \
        --ignore=tests/browser \
        --ignore=tests/test_bulk_vial_browser.py \
        --durations=10 \
        --tb=short
    ;;

browser)
    echo "=== ISOLATED BROWSER TESTS ==="

    "$PYTHON" -m pytest \
        -q tests/test_bulk_vial_browser.py \
        --tb=short
    ;;

all)
    echo "=== COMPLETE ISOLATED REGRESSION ==="

    "$PYTHON" -m compileall -q app

    "$PYTHON" -m pytest \
        -q tests \
        --ignore=tests/browser \
        --durations=10 \
        --tb=short
    ;;

live)
    echo "=== LIVE TRACKER BROWSER TESTS ==="

    "$PYTHON" -m pytest \
        -q tests/browser \
        --tb=short
    ;;

none)
    echo "=== SYNTAX CHECK ONLY ==="

    "$PYTHON" -m compileall -q app
    ;;

*)
    echo "Usage: $0 {quick|full|browser|all|live|none}"
    exit 2
    ;;

esac

echo
echo "Elapsed: $((SECONDS - start)) seconds"
