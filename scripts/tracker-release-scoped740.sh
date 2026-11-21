#!/usr/bin/env bash
# Release 740: equipment MACD/API + mobile CSS change-scoped qualification.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "${TRACKER_DATA_DIR:-}" == /tmp/* ]] ||
  { echo "Release 740 requires isolated source/data" >&2; exit 2; }
for script in scripts/tracker-qualify740.sh scripts/tracker-install740.sh \
  scripts/tracker-release-scoped740.sh scripts/tracker-release.sh; do
  bash -n "$script"
done
"$PY" -m py_compile app/routers/workouts654.py tests/test_release740_equipment_macd_mobile.py
"$PY" -c 'from pathlib import Path; from jinja2 import Environment; e=Environment(); [e.parse(Path(p).read_text(encoding="utf-8")) for p in ("app/templates/workouts654.html",)]'
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release740_equipment_macd_mobile.py \
  tests/test_workouts654.py \
  tests/test_workouts655.py \
  tests/test_release714_routine_alignment.py \
  tests/test_release739_workout_food_macd_mobile.py
echo "RELEASE_740_EQUIPMENT_MACD_MOBILE_TESTS=PASSED"
echo "RELEASE_740_SCOPED_QUALIFICATION=PASSED_NOT_FULL_SUITE"
