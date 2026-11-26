#!/usr/bin/env bash
# Release 790: integrated daily workspace, notes and browser regression only.
set -Eeuo pipefail
umask 077
PY="${1:-}"
[[ -n "$PY" && -x "$PY" ]] || { echo "RELEASE_790_BLOCKED=Python missing" >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q --tb=short --disable-warnings \
 "tests/test_integrated_daily790.py" \
 "tests/test_calendar_action_buttons787.py" \
 "tests/test_calendar_quick_dose786.py" \
 "tests/test_calendar_day_navigation789.py" \
 "tests/test_calendar_workbench.py" \
 "tests/test_dashboard_dose_shortcuts.py" \
 "tests/test_release783_reconciliation.py" \
 "tests/test_release731_tablet_tracking.py" \
 "tests/test_release778_regimen_return.py" \
 "tests/test_release765_daily_actions.py" \
 "tests/test_mobile_quick528.py" \
 "tests/test_mobile_quick_actions701.py" \
 "tests/test_release776_google_tasks_focus.py" \
 "tests/test_spacing529.py" \
 "tests/test_mobile_daily509.py" \
 "tests/test_core_user_db394.py::test_every_core_dependency_is_scoped[calendar-5]"
echo "RELEASE_790_SCOPED=PASSED"
