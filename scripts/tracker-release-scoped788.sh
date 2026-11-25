#!/usr/bin/env bash
# Release 788: Google completion single confirmation, notes and browser regression only.
set -Eeuo pipefail
umask 077
PY="${1:-}"
[[ -n "$PY" && -x "$PY" ]] || { echo "RELEASE_788_BLOCKED=Python missing" >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q --tb=short --disable-warnings \
 "tests/test_release783_reconciliation.py" \
 "tests/test_calendar_workbench.py" \
 "tests/test_calendar_action_buttons787.py"
echo "RELEASE_788_SCOPED=PASSED"
