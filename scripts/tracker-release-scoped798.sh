#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
PY="${1:?Python required}"
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q --tb=no --disable-warnings tests/test_daily_calendar_performance798.py tests/test_workflow_consolidation794.py
echo "RELEASE_798_SCOPED=PASSED"
