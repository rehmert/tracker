#!/usr/bin/env bash
# Release 693: Workout-only QR retirement and adjacent Data Quality QA.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" ]] || { echo "Run in isolated candidate source root" >&2; exit 2; }
bash -n scripts/tracker-release.sh
bash -n scripts/tracker-release-scoped693.sh
bash -n scripts/tracker-preview693.sh
"$PY" -m py_compile \
  app/routers/workouts654.py \
  app/routers/data_quality674.py \
  tests/test_workouts654.py \
  tests/test_workouts656.py \
  tests/test_workout_no_camera692.py \
  tests/test_workout_no_qr693.py \
  tests/test_integrated_productivity674.py \
  scripts/tracker-workout-qr-retirement-review693.py
"$PY" - <<'PY'
from jinja2 import Environment
from pathlib import Path
for name in ("workouts654.html", "workout_quick659.html", "data_quality674.html"):
    Environment().parse((Path("app/templates") / name).read_text(encoding="utf-8"))
print("RELEASE_693_JINJA_SYNTAX=PASSED")
PY
echo "RELEASE_693_TEST_SCOPE=WORKOUT_AND_DATA_QUALITY_FOCUSED_NO_FULL_SUITE"
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_workout_no_qr693.py \
  tests/test_workout_no_camera692.py \
  tests/test_workouts654.py \
  tests/test_workouts655.py \
  tests/test_workouts656.py \
  tests/test_workouts657.py \
  tests/test_workouts659.py \
  tests/test_integrated_productivity674.py
echo "RELEASE_693_WORKOUT_QR_RETIREMENT_SCOPED_TESTS=PASSED"
