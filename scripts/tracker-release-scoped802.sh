#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
PY="${1:?Python required}"
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q --tb=no --disable-warnings tests/test_benchmark800.py tests/test_performance802.py tests/test_workflow_consolidation794.py tests/test_daily_calendar_performance797.py
echo "RELEASE_802_SCOPED=PASSED"
