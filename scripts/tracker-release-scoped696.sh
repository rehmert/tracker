#!/usr/bin/env bash
# Release 696: one change-scoped qualification gate for 696–697 and 701–702.
# No full suite, downloads, installed data, or deployment side effects.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "$ROOT" != /opt/tracker ]] || {
  echo "Run in detached release candidate worktree" >&2
  exit 2
}

"$PY" -m py_compile tests/test_integrated_flow696.py tests/browser/test_integrated_flow696.py
"$PY" - <<'PY'
from pathlib import Path
from jinja2 import Environment
env = Environment()
pages = (
 "workout_quick659.html", "workouts654.html", "food.html", "doses.html",
 "vitals.html", "vials.html", "purchases.html", "coas.html", "labs.html",
)
for page in pages:
    env.parse(Path("app/templates", page).read_text(encoding="utf-8"))
css=Path("app/static/css/tracker-integrated-flow696.css").read_text(encoding="utf-8")
assert css.count("{") == css.count("}")
print("RELEASE_696_JINJA_CSS_SYNTAX=PASSED")
PY
command -v node >/dev/null 2>&1 || {
  echo "Release 696 needs installed Node.js for syntax validation" >&2
  exit 2
}
node --check app/static/js/tracker-coa-find696.js
echo "RELEASE_696_JS_SYNTAX=PASSED"
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_integrated_flow696.py \
  tests/test_integrated_mobile_ux673.py::test_673_food_focus_preserves_every_existing_capability \
  tests/test_integrated_mobile_ux673.py::test_673_gym_keeps_recording_and_offline_sync_but_defers_advanced_tools \
  tests/test_integrated_mobile_ux673.py::test_673_inventory_uses_existing_purchase_mode_and_new_single_row_cards \
  tests/test_release604_preflight.py::test_604_vial_workflows_all_have_one_toolbar \
  tests/test_release603_inventory_purchase_navigation.py::test_603_vials_retain_all_bulk_tools_and_jump_open_sections \
  tests/test_release619_bundle.py::test_618_guides_are_read_only_and_original_forms_remain
echo "RELEASE_696_SOURCE_TESTS=PASSED"
echo "RELEASE_696_SCOPED=PASSED"
