#!/usr/bin/env bash
# Release 668: calendar + prior Workout guard, no full application test suite.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Expected configured Python executable" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && -d tests ]] || { echo "Requires isolated release worktree" >&2; exit 2; }
bash -n scripts/tracker-release668.sh
bash -n scripts/tracker-release-scoped668.sh
bash -n scripts/tracker-release.sh
bash -n scripts/tracker_prod_remote568.sh
"$PY" -m py_compile app/routers/calendar.py app/routers/workouts655.py app/routers/workouts663.py app/routers/workouts667.py app/routers/workouts668.py app/routers/workouts658.py app/routers/workouts659.py app/main.py app/workout_csv668.py app/workout_models668.py tests/test_calendar_sort668.py tests/test_workout_tools668.py tests/test_workout_csv668.py tests/test_workout_schedule668.py tests/test_workout_corrections668.py tests/test_workout_csv_history668.py
command -v node >/dev/null || { echo "Node.js is required for local-draft syntax validation" >&2; exit 2; }
node --check app/static/js/tracker-workout-drafts668.js
"$PY" - <<'PY'
from pathlib import Path
from jinja2 import Environment
for filename in (
    "calendar.html", "workout_program667.html", "workout_backfill658.html", "workout_routine_detail655.html",
    "workout_routines655.html", "workout_schedule668.html", "workout_corrections668.html",
    "workout_quick659.html", "workout_review663.html", "workout_insights668.html",
):
    Environment().parse((Path("app/templates") / filename).read_text(encoding="utf-8"))
print("RELEASE_668_CHANGED_TEMPLATE_SYNTAX=PASSED")
PY
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_calendar_sort668.py \
  tests/test_workout_tools668.py \
  tests/test_workout_csv668.py \
  tests/test_workout_schedule668.py \
  tests/test_workout_corrections668.py \
  tests/test_workout_csv_history668.py \
  tests/test_calendar_review_agenda.py \
  tests/test_workouts667.py \
  tests/test_workouts655.py \
  tests/test_workouts663.py
echo "RELEASE_668_FOCUSED_CALENDAR_AND_WORKOUT_REGRESSIONS=PASSED"
