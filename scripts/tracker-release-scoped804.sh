#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
PY="${1:?Python required}"
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q -s --tb=no --disable-warnings tests/test_visual_mobile_personalization804.py tests/test_design_system793.py tests/test_workflow_navigation803.py tests/test_workflow_consolidation794.py
echo "RELEASE_804_SCOPED=PASSED"
