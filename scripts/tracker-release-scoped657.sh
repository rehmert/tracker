#!/usr/bin/env bash
# Release 657: isolated, release-scoped gym-floor Workout qualification.
set -Eeuo pipefail
[[ "$#" == 1 && -x "$1" ]] || {
  echo "Usage: $0 PATH_TO_CONFIGURED_PYTHON" >&2; exit 2;
}
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && -d tests ]] || {
  echo "Run only in isolated candidate worktree" >&2; exit 2;
}
bash -n "$0"
bash -n scripts/tracker-workout-dev657.sh
bash -n scripts/tracker-release.sh
"$PY" -m py_compile \
  app/routers/workouts654.py app/routers/workouts657.py \
  scripts/tracker-workout-review657.py tests/test_workouts657.py
"$PY" - <<'PY'
from jinja2 import Environment
from pathlib import Path
for path in (
    Path("app/templates/workouts654.html"),
    Path("app/templates/workout_history654.html"),
    Path("app/templates/workout_progress656.html"),
):
    Environment().parse(path.read_text(encoding="utf-8"))
print("WORKOUT_657_JINJA_SYNTAX=PASSED")
PY
BASE=06b8be62f5be455df47be87bc5157b41fcac8783
TARGET="$(git rev-parse HEAD)"
"$PY" scripts/tracker-workout-review657.py \
  --root "$ROOT" --base "$BASE" --target "$TARGET"
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_workouts657.py \
  tests/test_workouts656.py \
  tests/test_workouts655.py \
  tests/test_workouts654.py \
  tests/test_workout_dev_backup655.py \
  tests/test_tracker_instance_check653.py \
  tests/test_release_workflow.py \
  tests/test_prod_parallel_release508.py \
  tests/test_release629_qa_cadence.py
echo "WORKOUT_657_CHANGE_SCOPED_TESTS=PASSED"
