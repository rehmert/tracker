#!/usr/bin/env bash
# Release 668: one change-scoped DEV qualification for all remaining workout improvements.
set -Eeuo pipefail
[[ "$#" == 1 && -x "$1" ]] || { echo "Usage: $0 PYTHON" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && -d tests ]] || {
  echo "Run only in isolated release candidate worktree" >&2; exit 2;
}

bash -n "$0"
bash -n scripts/tracker-release.sh
bash -n scripts/tracker_prod_remote568.sh
bash -n scripts/tracker-workout-dev668.sh
bash -n scripts/tracker-workout-promote668.sh
"$PY" -m py_compile \
  app/workout_models668.py \
  app/routers/workouts668_program.py \
  app/routers/workouts668_history.py \
  app/routers/workouts668_csv.py \
  app/routers/workouts668_offline.py \
  app/routers/workouts668_insights.py \
  app/routers/workouts654.py app/routers/workouts655.py \
  app/routers/workouts656.py app/routers/workouts659.py \
  app/routers/workouts664.py app/routers/dashboard.py \
  tests/test_workouts668.py tests/browser/test_workout_advanced668.py \
  scripts/tracker-workout-schema-review668.py
command -v node >/dev/null || {
  echo "Node required for Release 668 browser qualification" >&2; exit 2;
}
node --check app/static/js/tracker-workout-offline668.js
node --check app/static/js/tracker-workout-csv668.js
node --check app/static/js/tracker-workouts659.js
node --check app/static/js/tracker-workout-gym667.js
"$PY" - <<'PY'
from pathlib import Path
from jinja2 import Environment
paths = (
  "workout_programs668.html", "workout_insights668.html", "workout_data668.html",
  "workout_history654.html", "workout_routine_detail655.html", "workout_quick659.html",
  "workout_calendar664.html", "_workout_dashboard661.html",
  "workout_progress656.html", "workout_review663.html",
  "workout_program667.html", "dashboard.html",
)
for name in paths:
    Environment().parse((Path("app/templates") / name).read_text(encoding="utf-8"))
print("WORKOUT_668_JINJA_JS_PYTHON_SYNTAX=PASSED")
PY

BASE=9baa03fb521573ba17ec1853fb85d40a22895336
TARGET="$(git rev-parse HEAD)"
"$PY" scripts/tracker-workout-schema-review668.py \
  --root "$ROOT" --base "$BASE" --target "$TARGET"
echo "WORKOUT_668_SCHEMA_SOURCE_REVIEW=PASSED"

"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_workouts668.py \
  tests/test_workouts667.py \
  tests/test_workouts666.py \
  tests/test_workouts665.py \
  tests/test_workouts664.py \
  tests/test_workouts663.py \
  tests/test_workouts662.py \
  tests/test_workouts660.py \
  tests/test_workout_dashboard661.py \
  tests/test_workouts659.py \
  tests/test_workouts658.py \
  tests/test_workouts657.py \
  tests/test_workouts656.py \
  tests/test_workouts655.py \
  tests/test_workouts654.py \
  tests/test_workout_dev_backup655.py \
  tests/test_tracker_instance_check653.py \
  tests/test_release_workflow.py \
  tests/test_prod_parallel_release508.py \
  tests/test_release629_qa_cadence.py
echo "WORKOUT_668_BACKEND_AND_MIGRATION_REGRESSIONS=PASSED"

"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/browser/test_workout_advanced668.py \
  tests/browser/test_workout_program667.py \
  tests/browser/test_workout_targets666.py \
  tests/browser/test_workout_plan665.py \
  tests/browser/test_workout_calendar664.py \
  tests/browser/test_workouts_quick662.py \
  tests/browser/test_workouts_quick659.py \
  tests/browser/test_workout_dashboard661.py
echo "WORKOUT_668_PHONE_BROWSER_REGRESSIONS=PASSED"
