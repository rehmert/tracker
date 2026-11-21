#!/usr/bin/env bash
# Release 719: only scoped workout delete and dashboard pagination tests.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "${TRACKER_DATA_DIR:-}" == /tmp/* ]] ||
  { echo "Release 719 requires isolated worktree and temporary DB" >&2; exit 2; }

for script in \
  scripts/tracker-release.sh \
  scripts/tracker-release-scoped719.sh \
  scripts/tracker-qualify719.sh \
  scripts/tracker-install719.sh \
  scripts/tracker-browser-qualify.sh \
  scripts/tracker_prod_remote568.sh; do
  bash -n "$script"
done
"$PY" -m py_compile \
  app/routers/workouts668.py \
  app/routers/dashboard.py \
  app/workout_dashboard661.py \
  tests/test_release719_workout_history.py \
  tests/browser/test_workout_manage719.py \
  tests/test_workout_dashboard661.py \
  tests/test_workout_activity_cards678.py \
  tests/test_browser_qualification511.py

"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release719_workout_history.py \
  tests/test_workout_dashboard661.py \
  tests/test_workout_activity_cards678.py \
  tests/test_overview_css_order682.py \
  tests/test_overview_density690.py \
  tests/test_workout_dashboard668.py \
  tests/test_workouts654.py \
  tests/test_workouts663.py \
  tests/test_workout_corrections668.py \
  tests/test_workouts657.py \
  tests/browser/test_workout_dashboard661.py \
  tests/test_browser_qualification511.py::test_511_every_browser_module_in_disposable_qualification
echo "RELEASE_719_SCOPED_BACKEND=PASSED"

bash scripts/tracker-browser-qualify.sh "$ROOT" "$PY" \
  --targeted-strict workout-manage719
echo "RELEASE_719_SCOPED_BROWSER=PASSED"
echo "RELEASE_719_SCOPED_QUALIFICATION=PASSED_NOT_FULL_SUITE"
