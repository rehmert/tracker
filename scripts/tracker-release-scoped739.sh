#!/usr/bin/env bash
# Release 739: change-scoped Workout/Food MACD, mobile actions, CSS consolidation.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "${TRACKER_DATA_DIR:-}" == /tmp/* ]] ||
  { echo "Release 739 requires isolated source/data" >&2; exit 2; }
for script in scripts/tracker-qualify739.sh scripts/tracker-install739.sh \
  scripts/tracker-release-scoped739.sh scripts/tracker-release.sh; do
  bash -n "$script"
done
"$PY" -m py_compile app/routers/workouts655.py app/routers/food.py \
  tests/test_release739_workout_food_macd_mobile.py
"$PY" -c 'from pathlib import Path; from jinja2 import Environment; e=Environment(); [e.parse(Path(p).read_text(encoding="utf-8")) for p in ("app/templates/workout_routines655.html","app/templates/workout_routine_detail655.html","app/templates/food_saved_edit669.html")]'
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_saved_food_mobile_actions702.py \
  tests/test_food_saved_edit669.py \
  tests/test_release739_workout_food_macd_mobile.py \
  tests/test_release714_routine_alignment.py \
  tests/test_workouts655.py \
  tests/browser/test_saved_food_mobile_actions702.py \
  tests/test_food_mobile424.py
echo "RELEASE_739_INTEGRATED_MACD_MOBILE_TESTS=PASSED"
echo "RELEASE_739_SCOPED_QUALIFICATION=PASSED_NOT_FULL_SUITE"
