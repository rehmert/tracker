#!/usr/bin/env bash
set -Eeuo pipefail

APP=/opt/tracker
PY="$APP/.venv/bin/python"

cd "$APP"

"$PY" - <<'PY'
from importlib.util import find_spec
if find_spec('playwright') is None:
    raise SystemExit(
        'Playwright is unavailable. Browser QA is required '
        'before release promotion.'
    )
print('PASS: Playwright installed')
PY

export TRACKER_TEST_URL="${
    TRACKER_TEST_URL:-http://127.0.0.1:8000
}"

"$PY" -m pytest -q --tb=short --maxfail=1 \
    tests/browser/test_pk_smoke_281.py
