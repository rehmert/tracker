#!/usr/bin/env bash
# Release 789: calendar day navigation, notes and browser regression only.
set -Eeuo pipefail
umask 077
PY="${1:-}"
[[ -n "$PY" && -x "$PY" ]] || { echo "RELEASE_789_BLOCKED=Python missing" >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q --tb=short --disable-warnings \
 "tests/test_calendar_day_navigation789.py" \
 "tests/test_calendar_workbench.py" \
 "tests/test_calendar_action_buttons787.py" \
 "tests/test_calendar_quick_dose786.py" \
 "tests/test_calendar_day_navigation.py::test_navigation_counts_visible_days_only" \
 "tests/test_calendar_day_navigation.py::test_navigation_respects_filters" \
 "tests/test_calendar_day_navigation.py::test_navigation_does_not_mutate_records"
echo "RELEASE_789_SCOPED=PASSED"
