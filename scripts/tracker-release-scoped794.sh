#!/usr/bin/env bash
# Release 794: consolidated planning and daily workflows, notes and browser regression only.
set -Eeuo pipefail
umask 077
PY="${1:-}"
[[ -n "$PY" && -x "$PY" ]] || { echo "RELEASE_794_BLOCKED=Python missing" >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q --tb=short --disable-warnings \
 "tests/test_workflow_consolidation794.py" \
 "tests/test_labs_overview.py" \
 "tests/test_release778_regimen_return.py" \
 "tests/test_release775_google_tasks_navigation.py" \
 "tests/test_release766_combined.py" \
 "tests/test_workouts659.py" \
 "tests/test_workouts662.py" \
 "tests/test_release782_compact_gym.py" \
 "tests/test_protocol_schedule_preview.py" \
 "tests/test_protocol_inventory_handoff.py" \
 "tests/test_integrated_daily790.py" \
 "tests/test_compact_daily_actions791.py" \
 "tests/test_calendar_action_buttons787.py" \
 "tests/test_consolidated_workspaces792.py" \
 "tests/test_release602_mobile_bundle.py::test_602_dose_draft_fastpath_and_original_form" \
 "tests/test_release602_mobile_bundle.py::test_602_mobile_guidance_has_no_write_or_prefill_actions"
echo "RELEASE_794_SCOPED=PASSED"
