#!/usr/bin/env bash
# Release 723: exact CSS order, responsive visual parity and signed Workout flows.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "${TRACKER_DATA_DIR:-}" == /tmp/* ]] ||
  { echo "Release 723 requires isolated worktree and data" >&2; exit 2; }
for file in scripts/tracker-qualify723.sh scripts/tracker-install723.sh \
    scripts/tracker-release-scoped723.sh scripts/tracker-release.sh \
    scripts/tracker-browser-qualify.sh; do
  bash -n "$file"
done
"$PY" -m py_compile \
  tests/test_release723_css_consolidation.py tests/browser/test_release723_css_parity.py
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release723_css_consolidation.py \
  tests/test_release722_gym_focus.py \
  tests/test_workouts662.py \
  tests/test_integrated_mobile_ux673.py \
  tests/test_workouts659.py \
  tests/browser/test_release723_css_parity.py \
  tests/browser/test_workouts_quick662.py \
  tests/browser/test_workout_targets666.py \
  tests/browser/test_workout_program667.py \
  tests/test_integrated_mobile_browser673.py
echo "RELEASE_723_SCOPED_BACKEND_BROWSER=PASSED"
# Real authenticated workflow and session management, HTTP and HTTPS.
bash scripts/tracker-browser-qualify.sh "$ROOT" "$PY" --targeted-strict workout-active716
bash scripts/tracker-browser-qualify.sh "$ROOT" "$PY" --targeted-strict workout-manage719
echo "RELEASE_723_SCOPED_SIGNED_BROWSER=PASSED"
echo "RELEASE_723_SCOPED_QUALIFICATION=PASSED_NOT_FULL_SUITE"
