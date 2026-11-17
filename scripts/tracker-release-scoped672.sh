#!/usr/bin/env bash
# Release 672: focused cross-module action-button consistency and saved-food edit UX.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Expected configured Python executable" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && -d tests ]] || { echo "Requires isolated candidate worktree" >&2; exit 2; }
bash -n scripts/tracker-release-scoped672.sh
bash -n scripts/tracker-preview672.sh
bash -n scripts/tracker-release672.sh
"$PY" -m py_compile tests/test_food_saved_edit669.py
"$PY" - <<'PY'
from pathlib import Path
from jinja2 import Environment
Environment().parse(Path("app/templates/food.html").read_text(encoding="utf-8"))
print("RELEASE_672_FOOD_TEMPLATE_SYNTAX=PASSED")
PY
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_food_action670.py \
  tests/test_food_saved_edit669.py \
  tests/test_ui_action_cleanup672.py \
  tests/test_food_edit_buttons671.py \
  tests/test_food_quick375.py \
  tests/test_food_bundle376.py \
  tests/test_workout_tools668.py
echo "RELEASE_672_FOCUSED_FOOD_ACTION_REGRESSIONS=PASSED"
