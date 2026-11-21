#!/usr/bin/env bash
# Release 724: focused mobile Workout navigation tests, never full suite.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "${TRACKER_DATA_DIR:-}" == /tmp/* ]] ||
  { echo "Release 724 requires isolated source and disposable data" >&2; exit 2; }
for script in scripts/tracker-release.sh scripts/tracker-qualify724.sh \
    scripts/tracker-install724.sh scripts/tracker-release-scoped724.sh \
    scripts/tracker-browser-qualify.sh; do bash -n "$script"; done

"$PY" -m py_compile tests/test_release724_nav_dedup.py \
  tests/test_release723_css_consolidation.py tests/browser/test_release723_css_parity.py \
  tests/browser/test_workout_active716.py
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release724_nav_dedup.py tests/test_release723_css_consolidation.py \
  tests/test_release722_gym_focus.py tests/test_workouts659.py \
  tests/test_workouts662.py tests/test_integrated_mobile_ux673.py \
  tests/browser/test_release723_css_parity.py tests/test_overview_css_order682.py
echo "RELEASE_724_SCOPED_BACKEND=PASSED"
bash scripts/tracker-browser-qualify.sh "$ROOT" "$PY" --targeted-strict workout-active716
bash scripts/tracker-browser-qualify.sh "$ROOT" "$PY" --targeted-strict workout-manage719
echo "RELEASE_724_SCOPED_BROWSER=PASSED"
echo "RELEASE_724_SCOPED_QUALIFICATION=PASSED_NOT_FULL_SUITE"
