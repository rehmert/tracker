#!/usr/bin/env bash
# Release 658: isolated, change-scoped historical Workout qualification.
set -Eeuo pipefail
[[ "$#" == 1 && -x "$1" ]] || {
  echo "Usage: $0 PATH_TO_CONFIGURED_PYTHON" >&2; exit 2;
}
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && -d tests ]] || {
  echo "Run from isolated candidate worktree" >&2; exit 2;
}
bash -n "$0"
bash -n scripts/tracker-workout-dev658.sh
bash -n scripts/tracker-release.sh
"$PY" -m py_compile \
  app/routers/workouts658.py \
  scripts/tracker-workout-review658.py \
  tests/test_workouts658.py
command -v node >/dev/null || {
  echo "Node.js required for historical entry UI syntax qualification" >&2; exit 2;
}
node --check app/static/js/tracker-workouts658.js
"$PY" - <<'PY'
from pathlib import Path
from jinja2 import Environment
for path in (
    Path("app/templates/workout_backfill658.html"),
    Path("app/templates/workouts654.html"),
    Path("app/templates/workout_history654.html"),
    Path("app/templates/workout_progress656.html"),
):
    Environment().parse(path.read_text(encoding="utf-8"))
print("WORKOUT_658_JINJA_AND_JS_SYNTAX=PASSED")
PY

BASE=b9487d4b1fab176255b398833c51c9a2da79f042
TARGET="$(git rev-parse HEAD)"
"$PY" scripts/tracker-workout-review658.py \
  --root "$ROOT" --base "$BASE" --target "$TARGET"
"$PY" -m pytest -q --tb=short --maxfail=1 \
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
echo "WORKOUT_658_CHANGE_SCOPED_TESTS=PASSED"
