#!/usr/bin/env bash
# Release 792: consolidated food, gym, inventory and health workspaces, notes and browser regression only.
set -Eeuo pipefail
umask 077
PY="${1:-}"
[[ -n "$PY" && -x "$PY" ]] || { echo "RELEASE_792_BLOCKED=Python missing" >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q --tb=short --disable-warnings \
 "tests/test_consolidated_workspaces792.py" \
 "tests/test_food_bundle376.py" \
 "tests/test_food_accordion382.py" \
 "tests/test_food_order383.py" \
 "tests/test_food_mobile424.py" \
 "tests/test_food_action670.py" \
 "tests/test_workouts659.py" \
 "tests/test_workouts662.py" \
 "tests/test_release782_compact_gym.py" \
 "tests/test_release722_gym_focus.py" \
 "tests/test_release725_rest_first.py" \
 "tests/test_protocol_schedule_preview.py" \
 "tests/test_protocol_inventory_handoff.py" \
 "tests/test_release762_progress.py" \
 "tests/test_release766_combined.py::test_766_routes_and_templates_render_with_existing_auth" \
 "tests/test_release603_inventory_purchase_navigation.py::test_603_purchase_list_form_and_filters_are_preserved" \
 "tests/test_release619_bundle.py::test_618_guides_are_read_only_and_original_forms_remain" \
 "tests/test_integrated_mobile_ux673.py" \
 "tests/test_compact_daily_actions791.py"
echo "RELEASE_792_SCOPED=PASSED"
