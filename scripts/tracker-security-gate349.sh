#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="${TRACKER_TEST_PYTHON:-/opt/tracker/.venv/bin/python}"
cd "$ROOT"

"$PY" -m pytest -q --tb=long --maxfail=1 \
    tests/test_release_346_349.py \
    tests/test_csrf_browser_integration.py \
    tests/test_csrf_reporting.py \
    tests/test_csrf_form_body_report.py
