#!/usr/bin/env bash
# Release 667: full change-scoped validation of one bundled Workout program.
set -Eeuo pipefail
[[ "$#" == 1 && -x "$1" ]] || {
  echo "Usage: $0 PATH_TO_CONFIGURED_PYTHON" >&2; exit 2;
}
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && -d tests ]] || {
  echo "Run only from isolated candidate worktree" >&2; exit 2;
}

bash -n "$0"
bash -n scripts/tracker-release.sh
bash -n scripts/tracker_prod_remote568.sh
bash -n scripts/tracker-workout-dev667.sh

"$PY" -m py_compile \
  app/workout_models667.py app/workout_program667.py \
  app/routers/workouts667.py app/routers/workouts654.py \
  app/routers/workouts655.py app/routers/workouts657.py \
  app/routers/workouts659.py app/routers/workouts663.py \
  scripts/tracker-workout-schema-review667.py \
  tests/test_workouts667.py tests/browser/test_workout_program667.py

command -v node >/dev/null || {
  echo "Node.js required for Workout 667 browser script syntax" >&2; exit 2;
}
node --check app/static/js/tracker-workout-program667.js
node --check app/static/js/tracker-workout-gym667.js
node --check app/static/js/tracker-workouts659.js
node --check app/static/js/tracker-workout-plan665.js
node --check app/static/js/tracker-workout-targets666.js

"$PY" - <<'PY'
from pathlib import Path
from jinja2 import Environment
for name in (
    "workout_program667.html",
    "workout_quick659.html",
    "workout_review663.html",
    "workouts654.html",
    "workout_routine_detail655.html",
    "workout_routines655.html",
    "workout_plan665.html",
    "workout_calendar664.html",
):
    Environment().parse((Path("app/templates") / name).read_text(encoding="utf-8"))
print("WORKOUT_667_TEMPLATE_JS_AND_PYTHON_SYNTAX=PASSED")
PY

BASE=4062afbc2ca4273d2fdadaab17c804c477a9fc08
TARGET="$(git rev-parse HEAD)"
"$PY" scripts/tracker-workout-schema-review667.py \
  --root "$ROOT" --base "$BASE" --target "$TARGET"
echo "WORKOUT_667_SCHEMA_GUARD=PASSED"

"$PY" -m pytest -q --tb=short --maxfail=1 \
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
echo "WORKOUT_667_SCOPED_BACKEND_AND_SCHEMA_REGRESSIONS=PASSED"

"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/browser/test_workout_program667.py \
  tests/browser/test_workout_targets666.py \
  tests/browser/test_workout_plan665.py \
  tests/browser/test_workout_calendar664.py \
  tests/browser/test_workouts_quick662.py \
  tests/browser/test_workouts_quick659.py \
  tests/browser/test_workout_dashboard661.py
echo "WORKOUT_667_CHROMIUM_MOBILE_REGRESSIONS=PASSED"
