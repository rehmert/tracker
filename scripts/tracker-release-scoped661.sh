#!/usr/bin/env bash
# Release 661: isolated, source-pinned Dashboard Workout qualification.
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
bash -n scripts/tracker-workout-dev661.sh
bash -n scripts/tracker-release.sh
"$PY" -m py_compile \
  app/workout_dashboard661.py \
  scripts/tracker-workout-review661.py \
  tests/test_workout_dashboard661.py \
  tests/browser/test_workout_dashboard661.py
"$PY" - <<'PY'
from pathlib import Path
from jinja2 import Environment
for name in (
    "app/templates/dashboard.html",
    "app/templates/_workout_dashboard661.html",
    "app/templates/workouts654.html",
    "app/templates/workout_quick659.html",
    "app/templates/workout_analytics660.html",
):
    Environment().parse(Path(name).read_text(encoding="utf-8"))
print("WORKOUT_661_DASHBOARD_JINJA_SYNTAX=PASSED")
PY

BASE=6a11a1a76a3d32d64bd8b98788dcc2eab4c0bece
TARGET="$(git rev-parse HEAD)"
"$PY" scripts/tracker-workout-review661.py \
  --root "$ROOT" --base "$BASE" --target "$TARGET"

"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_workout_dashboard661.py \
  tests/test_release599_dashboard_polish.py \
  tests/test_release598_dashboard_density.py \
  tests/test_dashboard_dose_shortcuts.py \
  tests/test_today_dashboard.py \
  tests/test_workouts660.py \
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
echo "WORKOUT_661_CHANGE_SCOPED_TESTS=PASSED"

"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/browser/test_workout_dashboard661.py
echo "WORKOUT_661_PHONE_DASHBOARD=PASSED"
