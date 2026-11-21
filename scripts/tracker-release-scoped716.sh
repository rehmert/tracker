#!/usr/bin/env bash
# Release 716: scoped active workout editor and Add Machine, disposable QA only.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python executable required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "${TRACKER_DATA_DIR:-}" == /tmp/* ]] ||
  { echo "Release 716 requires isolated source and disposable data" >&2; exit 2; }

for script in \
  scripts/tracker-release.sh \
  scripts/tracker-release-scoped716.sh \
  scripts/tracker-qualify716.sh \
  scripts/tracker-install716.sh \
  scripts/tracker-browser-qualify.sh \
  scripts/tracker_prod_remote568.sh; do
  bash -n "$script"
done

"$PY" -m py_compile \
  app/routers/workouts659.py \
  tests/test_release716_active_workout.py \
  tests/browser/test_workout_active716.py \
  tests/test_browser_qualification511.py

"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release716_active_workout.py \
  tests/test_workouts654.py \
  tests/test_workouts655.py \
  tests/test_workouts659.py \
  tests/test_workout_guides668.py \
  tests/test_release714_routine_alignment.py \
  tests/test_browser_qualification511.py::test_511_every_browser_module_in_disposable_qualification

echo "RELEASE_716_SCOPED_BACKEND=PASSED"

bash scripts/tracker-browser-qualify.sh "$ROOT" "$PY" \
  --targeted-strict workout-active716
echo "RELEASE_716_SCOPED_BROWSER=PASSED"
echo "RELEASE_716_SCOPED_QUALIFICATION=PASSED_NOT_FULL_SUITE"
