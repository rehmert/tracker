#!/usr/bin/env bash
# Release 786: calendar quick dose, notes and browser regression only.
set -Eeuo pipefail
umask 077
PY="${1:-}"
[[ -n "$PY" && -x "$PY" ]] || { echo "RELEASE_786_BLOCKED=Python missing" >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q --tb=short --disable-warnings \
 "tests/test_calendar_quick_dose786.py" \
 "tests/test_calendar_workbench.py" \
 "tests/test_calendar_mobile_dose_369.py" \
 "tests/test_calendar_auto_vial.py" \
 "tests/test_calendar_vial_handoff.py" \
 "tests/test_release756_calendar_vial_units.py" \
 "tests/test_release710_unified_blend_dose.py" \
 "tests/test_release783_reconciliation.py" \
 "tests/test_core_user_db394.py::test_every_core_dependency_is_scoped[calendar-5]"
echo "RELEASE_786_SCOPED=PASSED"
