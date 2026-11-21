#!/usr/bin/env bash
# Release 738: integrated scoped Regimen MACD and mobile Food/Workout CSS tests.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "${TRACKER_DATA_DIR:-}" == /tmp/* ]] ||
  { echo "Release 738 requires isolated source/data" >&2; exit 2; }
for script in scripts/tracker-qualify738.sh scripts/tracker-install738.sh \
    scripts/tracker-release-scoped738.sh scripts/tracker-release.sh; do
  bash -n "$script"
done
"$PY" -m py_compile app/routers/regimen635.py tests/test_release738_integrated_macd_mobile.py
"$PY" -c 'from pathlib import Path; from jinja2 import Environment; e=Environment(); [e.parse(Path(p).read_text(encoding="utf-8")) for p in ("app/templates/regimen635.html","app/templates/food.html","app/templates/workouts654.html","app/templates/workout_quick659.html")]'
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release738_integrated_macd_mobile.py \
  tests/test_release737_native_regimen_disclosures.py \
  tests/test_release736_regimen_add_chevron.py \
  tests/test_release734_regimen_button_parity.py \
  tests/test_release733_regimen_macd_actions.py \
  tests/test_release732_medication_delete.py \
  tests/test_release731_tablet_tracking.py \
  tests/test_release635_regimen.py \
  tests/test_action_navigation675.py \
  tests/test_action_navigation_browser675.py \
  tests/test_integrated_flow696.py \
  tests/test_food_mobile374.py \
  tests/test_food_mobile424.py \
  tests/test_food_accordion382.py \
  tests/test_food_water425.py \
  tests/test_release723_css_consolidation.py \
  tests/test_workout_nav_density681.py
echo "RELEASE_738_INTEGRATED_MACD_MOBILE_TESTS=PASSED"
echo "RELEASE_738_SCOPED_QUALIFICATION=PASSED_NOT_FULL_SUITE"
