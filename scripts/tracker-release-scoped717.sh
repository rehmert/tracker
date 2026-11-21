#!/usr/bin/env bash
# Release 717: bounded completed-workout correction/removal qualification.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python executable required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "${TRACKER_DATA_DIR:-}" == /tmp/* ]] ||
  { echo "Release 717 requires isolated source and disposable data" >&2; exit 2; }

for script in \
  scripts/tracker-release.sh \
  scripts/tracker-release-scoped717.sh \
  scripts/tracker-qualify717.sh \
  scripts/tracker-install717.sh \
  scripts/tracker-browser-qualify.sh \
  scripts/tracker_prod_remote568.sh; do
  bash -n "$script"
done

"$PY" -m py_compile \
  app/routers/workouts668.py \
  tests/test_release717_completed_edit.py \
  tests/browser/test_workout_completed717.py \
  tests/test_browser_qualification511.py

"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release717_completed_edit.py \
  tests/test_workout_corrections668.py \
  tests/test_integrated_productivity674.py \
  tests/test_workouts663.py \
  tests/test_workouts657.py \
  tests/test_workouts654.py \
  tests/test_browser_qualification511.py::test_511_every_browser_module_in_disposable_qualification

echo "RELEASE_717_SCOPED_BACKEND=PASSED"

bash scripts/tracker-browser-qualify.sh "$ROOT" "$PY" \
  --targeted-strict workout-completed717
echo "RELEASE_717_SCOPED_BROWSER=PASSED"
echo "RELEASE_717_SCOPED_QUALIFICATION=PASSED_NOT_FULL_SUITE"
