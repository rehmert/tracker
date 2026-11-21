#!/usr/bin/env bash
# Release 725 isolated Gym Rest Timer DOM-order qualification.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "${TRACKER_DATA_DIR:-}" == /tmp/* ]] ||
  { echo "Release 725 requires isolated source and data" >&2; exit 2; }
for s in scripts/tracker-release.sh scripts/tracker-qualify725.sh \
  scripts/tracker-install725.sh scripts/tracker-release-scoped725.sh \
  scripts/tracker-browser-qualify.sh; do bash -n "$s"; done
"$PY" -m py_compile tests/test_release725_rest_first.py \
 tests/test_release722_gym_focus.py tests/test_release724_nav_dedup.py \
 tests/browser/test_workout_active716.py
"$PY" -m pytest -q --tb=short --maxfail=1 \
 tests/test_release725_rest_first.py tests/test_release724_nav_dedup.py \
 tests/test_release723_css_consolidation.py tests/test_release722_gym_focus.py \
 tests/test_workouts659.py tests/test_workouts662.py \
 tests/test_integrated_mobile_ux673.py \
 tests/browser/test_workouts_quick659.py
echo "RELEASE_725_SCOPED_BACKEND=PASSED"
bash scripts/tracker-browser-qualify.sh "$ROOT" "$PY" --targeted-strict workout-active716
bash scripts/tracker-browser-qualify.sh "$ROOT" "$PY" --targeted-strict workout-manage719
echo "RELEASE_725_SCOPED_BROWSER=PASSED"
echo "RELEASE_725_SCOPED_QUALIFICATION=PASSED_NOT_FULL_SUITE"
