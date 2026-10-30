#!/usr/bin/env bash
set -euo pipefail

cd /opt/tracker

export TRACKER_TEST_URL="${TRACKER_TEST_URL:-http://127.0.0.1:8000}"

echo "========================================"
echo "Tracker Browser Regression Tests"
echo "========================================"
echo "Target: $TRACKER_TEST_URL"
echo

.venv/bin/python - <<'CHECK'
import importlib.util
import sys

if importlib.util.find_spec("playwright") is None:
    sys.exit(
        "Playwright is not installed. "
        "Run: .venv/bin/python -m pip install playwright"
    )
CHECK

.venv/bin/python -m pytest \
    tests/browser \
    -v \
    -rs
