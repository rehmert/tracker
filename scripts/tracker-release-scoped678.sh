#!/usr/bin/env bash
# Release 678: Overview Workout Activity actual rendering + existing focused contracts.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python executable required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && -d tests ]] || { echo "Expected isolated candidate worktree" >&2; exit 2; }
bash -n scripts/tracker-release-scoped678.sh
bash -n scripts/tracker-preview678.sh
bash -n scripts/tracker-release678.sh
"$PY" -m py_compile tests/test_workout_activity_cards678.py tests/test_workout_activity_cards_browser678.py
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_workout_activity_cards678.py \
  tests/test_workout_activity_cards_browser678.py \
  tests/test_workout_dashboard661.py \
  tests/browser/test_workout_dashboard661.py \
  tests/test_action_navigation675.py \
  tests/test_shortcut_buttons676.py \
  tests/test_shortcut_buttons_browser676.py \
  tests/test_integrated_mobile_ux673.py
echo "RELEASE_678_WORKOUT_ACTIVITY_CARDS_QUALIFICATION=PASSED"
