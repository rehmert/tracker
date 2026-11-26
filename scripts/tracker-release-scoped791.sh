#!/usr/bin/env bash
# Release 791: compact daily action layout, notes and browser regression only.
set -Eeuo pipefail
umask 077
PY="${1:-}"
[[ -n "$PY" && -x "$PY" ]] || { echo "RELEASE_791_BLOCKED=Python missing" >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q --tb=short --disable-warnings \
 "tests/test_compact_daily_actions791.py" \
 "tests/test_integrated_daily790.py" \
 "tests/test_calendar_action_buttons787.py" \
 "tests/test_calendar_day_navigation789.py" \
 "tests/test_calendar_workbench.py"
echo "RELEASE_791_SCOPED=PASSED"
