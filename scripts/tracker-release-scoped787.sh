#!/usr/bin/env bash
# Release 787: calendar action buttons, notes and browser regression only.
set -Eeuo pipefail
umask 077
PY="${1:-}"
[[ -n "$PY" && -x "$PY" ]] || { echo "RELEASE_787_BLOCKED=Python missing" >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q --tb=short --disable-warnings \
 "tests/test_calendar_action_buttons787.py" \
 "tests/test_calendar_quick_dose786.py" \
 "tests/test_calendar_workbench.py" \
 "tests/test_calendar_mobile_dose_369.py" \
 "tests/test_release756_calendar_vial_units.py" \
 "tests/test_release742_consolidated_ux_performance.py::test_742_templates_have_single_css_request_per_bundle" \
 "tests/test_release741_integrated_macd_mobile.py::test_741_integrated_templates_parse_have_scoped_asset_and_real_actions[calendar.html]"
echo "RELEASE_787_SCOPED=PASSED"
