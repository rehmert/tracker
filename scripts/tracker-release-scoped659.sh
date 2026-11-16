#!/usr/bin/env bash
# Release 659: isolated, change-scoped rapid gym floor qualification.
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
bash -n scripts/tracker-workout-dev659.sh
bash -n scripts/tracker-release.sh
"$PY" -m py_compile \
  app/routers/workouts659.py \
  scripts/tracker-workout-review659.py \
  tests/test_workouts659.py \
  tests/browser/test_workouts_quick659.py
command -v node >/dev/null || {
  echo "Node.js required for new Gym Floor browser logic syntax" >&2; exit 2;
}
node --check app/static/js/tracker-workouts659.js
"$PY" - <<'PY'
from jinja2 import Environment
from pathlib import Path
for file in (
    Path("app/templates/workout_quick659.html"),
    Path("app/templates/workouts654.html"),
    Path("app/templates/workout_backfill658.html"),
    Path("app/templates/workout_progress656.html"),
):
    Environment().parse(file.read_text(encoding="utf-8"))
print("WORKOUT_659_JINJA_AND_JS_SYNTAX=PASSED")
PY

BASE=8ff6dea1ac470e73fa886984238d958954de6d27
TARGET="$(git rev-parse HEAD)"
"$PY" scripts/tracker-workout-review659.py \
  --root "$ROOT" --base "$BASE" --target "$TARGET"
"$PY" -m pytest -q --tb=short --maxfail=1 \
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
echo "WORKOUT_659_CHANGE_SCOPED_TESTS=PASSED"

# Mocked browser document, actual shipped JS, no external requests/DB writes.
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/browser/test_workouts_quick659.py
echo "WORKOUT_659_PHONE_CHROMIUM=PASSED"
