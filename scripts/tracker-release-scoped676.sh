#!/usr/bin/env bash
# Release 676: visually verify button tiles against Daily Shortcuts.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python executable required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && -d tests ]] || { echo "Expected isolated candidate worktree" >&2; exit 2; }
bash -n scripts/tracker-release-scoped676.sh
bash -n scripts/tracker-preview676.sh
bash -n scripts/tracker-release676.sh
"$PY" -m py_compile tests/test_shortcut_buttons676.py tests/test_shortcut_buttons_browser676.py
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_shortcut_buttons676.py \
  tests/test_shortcut_buttons_browser676.py \
  tests/test_action_navigation675.py \
  tests/test_action_navigation_browser675.py \
  tests/test_integrated_mobile_ux673.py \
  tests/test_mobile_daily509.py \
  tests/test_workouts659.py \
  tests/test_workouts663.py \
  tests/test_workouts664.py \
  tests/test_purchase_history_review.py
echo "RELEASE_676_DAILY_STYLE_SHORTCUTS_QUALIFICATION=PASSED"
