#!/usr/bin/env bash
# Release 673: integrated mobile UX qualification; no full application suite.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python executable required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && -d tests ]] || { echo "Expected isolated candidate worktree" >&2; exit 2; }
bash -n scripts/tracker-release-scoped673.sh
bash -n scripts/tracker-preview673.sh
bash -n scripts/tracker-release673.sh
"$PY" -m py_compile tests/test_integrated_mobile_ux673.py tests/test_integrated_mobile_browser673.py
"$PY" - <<'PY'
from pathlib import Path
from jinja2 import Environment
pages = (
    "base.html", "food.html", "workout_quick659.html",
    "purchases.html", "supplies.html", "coas.html",
)
for page in pages:
    Environment().parse((Path("app/templates") / page).read_text(encoding="utf-8"))
print("RELEASE_673_JINJA_SYNTAX=PASSED")
PY
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_integrated_mobile_ux673.py \
  tests/test_integrated_mobile_browser673.py \
  tests/test_mobile_app_shell507.py \
  tests/test_mobile_quick528.py \
  tests/test_mobile_dock_pointer603.py \
  tests/test_release600_mobile_usability.py \
  tests/test_release602_mobile_bundle.py \
  tests/test_release603_inventory_purchase_navigation.py \
  tests/test_purchase_history_review.py \
  tests/test_supply_stock_filters.py \
  tests/test_food_accordion382.py \
  tests/test_food_mobile424.py \
  tests/test_food_saved_edit669.py \
  tests/test_workouts659.py \
  tests/test_workouts667.py \
  tests/test_workout_tools668.py \
  tests/test_workout_offline668.py
echo "RELEASE_673_INTEGRATED_MOBILE_UX_QUALIFICATION=PASSED"
