#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
PY="${1:?Python required}"
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q --tb=no --disable-warnings tests/test_frontend_performance798.py tests/test_release764_compound_title_case.py tests/test_explanation_touch680.py tests/test_release598_dashboard_density.py tests/test_workflow_consolidation794.py
echo "RELEASE_798_SCOPED=PASSED"
