#!/usr/bin/env bash
# Recovery 677: requalify the CSS color parity and both relevant gates.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Expected configured Python" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && -d tests ]] || { echo "Expected isolated candidate worktree" >&2; exit 2; }
bash -n scripts/tracker-release677.sh
bash -n scripts/tracker-preview677.sh
bash -n scripts/tracker-release-scoped677.sh
"$PY" -m py_compile scripts/tracker_promote568.py tests/test_shortcut_buttons_browser676.py
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_shortcut_buttons676.py \
  tests/test_shortcut_buttons_browser676.py \
  tests/test_action_navigation675.py \
  tests/test_action_navigation_browser675.py \
  tests/test_integrated_mobile_ux673.py \
  tests/test_mobile_daily509.py \
  tests/test_purchase_history_review.py \
  tests/test_workouts659.py \
  tests/test_workouts663.py \
  tests/test_workouts664.py \
  tests/test_shortcut_recovery677.py
echo "RELEASE_677_RECOVERY_QUALIFICATION=PASSED"
