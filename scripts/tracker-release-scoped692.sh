#!/usr/bin/env bash
# Release 692: change-scoped Workout UI, equipment, logging and progress.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python required" >&2; exit 2; }
PY="$1"
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" ]] || { echo "Use isolated candidate worktree" >&2; exit 2; }
bash -n scripts/tracker-release.sh
bash -n scripts/tracker-release-scoped692.sh
bash -n scripts/tracker-preview692.sh
"$PY" -m py_compile \
  app/routers/workouts656.py \
  scripts/tracker-workout-camera-review692.py \
  tests/test_workouts656.py \
  tests/test_workout_no_camera692.py
"$PY" - <<'PY'
from pathlib import Path
from jinja2 import Environment
for template in ("workouts654.html", "workout_progress656.html"):
    Environment().parse((Path("app/templates") / template).read_text(encoding="utf-8"))
print("RELEASE_692_JINJA_SYNTAX=PASSED")
PY
echo "RELEASE_692_TEST_SCOPE=WORKOUT_FOCUSED_NO_FULL_SUITE"
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_workout_no_camera692.py \
  tests/test_workouts654.py \
  tests/test_workouts655.py \
  tests/test_workouts656.py \
  tests/test_workouts657.py \
  tests/test_workouts658.py \
  tests/test_workouts659.py
echo "RELEASE_692_WORKOUT_SCOPED_TESTS=PASSED"
