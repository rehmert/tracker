#!/usr/bin/env bash
# Release 714: scoped routine-editor layout validation, disposable QA only.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python executable required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "${TRACKER_DATA_DIR:-}" == /tmp/* ]] ||
  { echo "Release 714 requires isolated source and disposable data" >&2; exit 2; }

for script in \
  scripts/tracker-release.sh \
  scripts/tracker-release-scoped714.sh \
  scripts/tracker-qualify714.sh \
  scripts/tracker-install714.sh \
  scripts/tracker_prod_remote568.sh; do
  bash -n "$script"
done

"$PY" -m py_compile tests/test_release714_routine_alignment.py
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release714_routine_alignment.py \
  tests/test_workouts655.py \
  tests/test_workout_guides668.py \
  tests/test_browser_qualification511.py::test_511_every_browser_module_in_disposable_qualification

echo "RELEASE_714_SCOPED_BACKEND_BROWSER=PASSED"
echo "RELEASE_714_ROUTINE_GEOMETRY=PASSED"
echo "RELEASE_714_SCOPED_QUALIFICATION=PASSED_NOT_FULL_SUITE"
