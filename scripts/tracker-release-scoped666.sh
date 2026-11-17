#!/usr/bin/env bash
# Release 666: isolate Rapid Gym target preview and existing log safeguards.
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
bash -n scripts/tracker-workout-dev666.sh
bash -n scripts/tracker-release.sh
"$PY" -m py_compile \
  app/routers/workouts659.py \
  scripts/tracker-workout-review666.py \
  tests/test_workouts666.py \
  tests/browser/test_workout_targets666.py

command -v node >/dev/null || {
  echo "Node.js required for client-only script syntax checks" >&2; exit 2;
}
node --check app/static/js/tracker-workout-targets666.js
node --check app/static/js/tracker-workout-plan665.js

"$PY" - <<'PY'
from pathlib import Path
from jinja2 import Environment
for name in (
    "workout_quick659.html",
    "workout_plan665.html",
    "workout_routine_detail655.html",
    "workout_routines655.html",
    "workout_review663.html",
    "workout_calendar664.html",
    "dashboard.html",
):
    Environment().parse(
        (Path("app/templates") / name).read_text(encoding="utf-8")
    )
print("WORKOUT_666_JINJA_AND_JS_SYNTAX=PASSED")
PY

BASE=fe34a4060cd8b5933322d91d3e011206c87e21ef
TARGET="$(git rev-parse HEAD)"
"$PY" scripts/tracker-workout-review666.py \
  --root "$ROOT" --base "$BASE" --target "$TARGET"

"$PY" -m pytest -q --tb=short --maxfail=1 \
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
echo "WORKOUT_666_SCOPED_REGRESSIONS=PASSED"

"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/browser/test_workout_targets666.py \
  tests/browser/test_workout_plan665.py \
  tests/browser/test_workout_calendar664.py \
  tests/browser/test_workouts_quick662.py \
  tests/browser/test_workouts_quick659.py \
  tests/browser/test_workout_dashboard661.py
echo "WORKOUT_666_PHONE_CHROMIUM_REGRESSIONS=PASSED"
