#!/usr/bin/env bash
# Release 730: bounded Workout latest set query, scoped no-DEV-install QA.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "$TRACKER_DATA_DIR" == /tmp/* ]] ||
  { echo "Release 730 requires isolated source/data" >&2; exit 2; }
for s in scripts/tracker-release.sh scripts/tracker-qualify730.sh \
    scripts/tracker-install730.sh scripts/tracker-release-scoped730.sh; do
  bash -n "$s"
done
"$PY" -m py_compile app/routers/workouts654.py \
  tests/test_release730_workout_page_queries.py
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release730_workout_page_queries.py \
  tests/test_workouts654.py \
  tests/test_workout_dashboard661.py
echo "RELEASE_730_WORKOUT_QUERY_TESTS=PASSED"
echo "RELEASE_730_SCOPED_QUALIFICATION=PASSED_NOT_FULL_SUITE"
