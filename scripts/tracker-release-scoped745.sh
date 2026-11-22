#!/usr/bin/env bash
# Release 745 isolated, source-scoped validation.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "$TRACKER_DATA_DIR" == /tmp/* ]] ||
  { echo "Isolated source and /tmp data required" >&2; exit 2; }
for path in scripts/tracker-qualify745.sh scripts/tracker-install745.sh \
  scripts/tracker-release-scoped745.sh scripts/tracker-release.sh; do
  bash -n "$path"
done
"$PY" -B -m py_compile scripts/tracker-release-agent745.py \
  tests/test_release745_controller.py tests/test_release745_macd_css.py \
  app/routers/food.py
echo "RELEASE_745_COMPILE=PASSED"
"$PY" -B -m pytest -q --tb=short --maxfail=1 \
  tests/test_release745_controller.py tests/test_release745_macd_css.py || exit 42
echo "RELEASE_745_CONTROLLER_MACD_CSS=PASSED"
"$PY" -B -m pytest -q --tb=short --maxfail=1 \
  tests/test_food_water425.py \
  tests/test_release738_integrated_macd_mobile.py \
  tests/test_integrated_mobile_ux673.py \
  tests/test_release724_nav_dedup.py \
  tests/test_workouts662.py \
  tests/test_integrated_flow696.py \
  tests/test_action_navigation675.py \
  tests/test_release744_release_coordination.py || exit 43
echo "RELEASE_745_HISTORICAL_MACD_CONTROLLER=PASSED"
"$PY" -B -m pytest -q --tb=short --maxfail=1 \
  tests/test_release743_security_deps_chain_css.py \
  -k "stage_chain or immutable_receipts or cumulative_dev_ahead_of_prod" || exit 44
echo "RELEASE_745_STAGE_CHAIN_REGRESSION=PASSED"
echo "RELEASE_745_SCOPED_QA=PASSED_NOT_FULL_SUITE"
