#!/usr/bin/env bash
# Release 675: focused mobile action navigation and shortened UX copy.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Expected configured Python executable" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && -d tests ]] || { echo "Expected isolated candidate worktree" >&2; exit 2; }
bash -n scripts/tracker-release-scoped675.sh
bash -n scripts/tracker-preview675.sh
bash -n scripts/tracker-release675.sh
"$PY" -m py_compile tests/test_action_navigation675.py tests/test_action_navigation_browser675.py
"$PY" - <<'PY'
from pathlib import Path
from jinja2 import Environment
pages = (
    "workouts654.html", "workout_quick659.html", "workout_review663.html",
    "workout_analytics660.html", "workout_calendar664.html",
    "workout_program667.html", "quick_entry.html", "purchases.html",
)
for page in pages:
    print(f"RELEASE_675_JINJA_CHECK={page}", flush=True)
    Environment().parse((Path("app/templates") / page).read_text(encoding="utf-8"))
print("RELEASE_675_JINJA_SYNTAX=PASSED")
PY
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_action_navigation675.py \
  tests/test_action_navigation_browser675.py \
  tests/test_integrated_mobile_ux673.py \
  tests/test_release604_preflight.py \
  tests/test_workouts656.py \
  tests/test_workouts658.py \
  tests/test_workouts659.py \
  tests/test_workouts660.py \
  tests/test_workouts663.py \
  tests/test_workouts664.py \
  tests/test_workouts667.py \
  tests/test_workout_tools668.py \
  tests/test_purchase_history_review.py \
  tests/test_release603_inventory_purchase_navigation.py
echo "RELEASE_675_NAVIGATION_COPY_QUALIFICATION=PASSED"
