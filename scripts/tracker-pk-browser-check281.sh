#!/usr/bin/env bash
set -Eeuo pipefail

APP=/opt/tracker
PY="$APP/.venv/bin/python"

cd "$APP"

export TRACKER_TEST_URL="${TRACKER_TEST_URL:-http://127.0.0.1:8000}"

# Delegated smoke test: tests/browser/test_pk_smoke_281.py
"$PY" scripts/tracker-browser-auth301.py
