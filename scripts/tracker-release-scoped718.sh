#!/usr/bin/env bash
# Release 718: scoped correction of recorded machine identity in completed sessions.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python executable required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "${TRACKER_DATA_DIR:-}" == /tmp/* ]] ||
  { echo "Release 718 requires disposable source and data" >&2; exit 2; }

for script in \
  scripts/tracker-release.sh \
  scripts/tracker-release-scoped718.sh \
  scripts/tracker-qualify718.sh \
  scripts/tracker-install718.sh \
  scripts/tracker-browser-qualify.sh \
  scripts/tracker_prod_remote568.sh; do
  bash -n "$script"
done

"$PY" -m py_compile \
  app/routers/workouts668.py \
  tests/test_release717_completed_edit.py \
  tests/browser/test_workout_machine718.py \
  tests/test_browser_qualification511.py

"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release717_completed_edit.py \
  tests/test_workout_corrections668.py \
  tests/test_integrated_productivity674.py \
  tests/test_workouts663.py \
  tests/test_workouts657.py \
  tests/test_browser_qualification511.py::test_511_every_browser_module_in_disposable_qualification

echo "RELEASE_718_SCOPED_BACKEND=PASSED"
bash scripts/tracker-browser-qualify.sh "$ROOT" "$PY" \
  --targeted-strict workout-machine718
echo "RELEASE_718_SCOPED_BROWSER=PASSED"
echo "RELEASE_718_SCOPED_QUALIFICATION=PASSED_NOT_FULL_SUITE"
