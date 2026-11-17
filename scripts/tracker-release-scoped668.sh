#!/usr/bin/env bash
# Release 668: calendar + prior Workout guard, no full application test suite.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Expected configured Python executable" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && -d tests ]] || { echo "Requires isolated release worktree" >&2; exit 2; }
bash -n scripts/tracker-release668.sh
bash -n scripts/tracker-release-scoped668.sh
bash -n scripts/tracker-release.sh
bash -n scripts/tracker_prod_remote568.sh
"$PY" -m py_compile app/routers/calendar.py tests/test_calendar_sort668.py
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_calendar_sort668.py \
  tests/test_calendar_review_agenda.py \
  tests/test_workouts667.py
echo "RELEASE_668_FOCUSED_CALENDAR_AND_WORKOUT_REGRESSIONS=PASSED"
