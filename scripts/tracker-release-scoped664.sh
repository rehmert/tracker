#!/usr/bin/env bash
# Release 664: isolated, read-only Workout Calendar DEV qualification.
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
bash -n scripts/tracker-workout-dev664.sh
bash -n scripts/tracker-release.sh
"$PY" -m py_compile \
  app/routers/workouts664.py \
  scripts/tracker-workout-review664.py \
  tests/test_workouts664.py \
  tests/browser/test_workout_calendar664.py
"$PY" - <<'PY'
from pathlib import Path
from jinja2 import Environment
for name in (
    "workout_calendar664.html",
    "workouts654.html",
    "_workout_dashboard661.html",
    "workout_review663.html",
    "workout_analytics660.html",
    "workout_quick659.html",
    "dashboard.html",
):
    Environment().parse(
        (Path("app/templates") / name).read_text(encoding="utf-8")
    )
print("WORKOUT_664_JINJA_SYNTAX=PASSED")
PY

BASE=20b9c0599ebf9ff4ea05ccddcd7130beaf6027a1
TARGET="$(git rev-parse HEAD)"
"$PY" scripts/tracker-workout-review664.py \
  --root "$ROOT" --base "$BASE" --target "$TARGET"

"$PY" -m pytest -q --tb=short --maxfail=1 \
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
  tests/test_release599_dashboard_polish.py \
  tests/test_release598_dashboard_density.py \
  tests/test_dashboard_dose_shortcuts.py \
  tests/test_workout_dev_backup655.py \
  tests/test_tracker_instance_check653.py \
  tests/test_release_workflow.py \
  tests/test_prod_parallel_release508.py \
  tests/test_release629_qa_cadence.py
echo "WORKOUT_664_CHANGE_SCOPED_REGRESSIONS=PASSED"

"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/browser/test_workout_calendar664.py \
  tests/browser/test_workouts_quick662.py \
  tests/browser/test_workouts_quick659.py \
  tests/browser/test_workout_dashboard661.py
echo "WORKOUT_664_CHROMIUM_PHONE_REGRESSIONS=PASSED"
