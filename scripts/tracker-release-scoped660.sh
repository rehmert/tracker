#!/usr/bin/env bash
# Release 660: isolated completed-only strength analytics qualification.
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
bash -n scripts/tracker-workout-dev660.sh
bash -n scripts/tracker-release.sh
"$PY" -m py_compile \
  app/routers/workouts660.py \
  scripts/tracker-workout-review660.py \
  tests/test_workouts660.py
"$PY" - <<'PY'
from pathlib import Path
from jinja2 import Environment
for path in (
    "app/templates/workout_analytics660.html",
    "app/templates/workouts654.html",
    "app/templates/workout_progress656.html",
    "app/templates/workout_quick659.html",
    "app/templates/workout_backfill658.html",
):
    Environment().parse(Path(path).read_text(encoding="utf-8"))
print("WORKOUT_660_JINJA_SYNTAX=PASSED")
PY
BASE=a02b70bb085533ff4ec23bae5e2bde9b25e40360
TARGET="$(git rev-parse HEAD)"
"$PY" scripts/tracker-workout-review660.py \
  --root "$ROOT" --base "$BASE" --target "$TARGET"

"$PY" -m pytest -q --tb=short --maxfail=1 \
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
echo "WORKOUT_660_CHANGE_SCOPED_TESTS=PASSED"

# Existing mobile gym-floor functionality is unchanged but remains qualified.
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/browser/test_workouts_quick659.py
echo "WORKOUT_660_GYM_FLOOR_BROWSER_REGRESSION=PASSED"
