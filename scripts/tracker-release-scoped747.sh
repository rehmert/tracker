#!/usr/bin/env bash
# Release 747: final focused acceptance against detached/private candidate only.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "$TRACKER_DATA_DIR" == /tmp/* ]] ||
  { echo "Disposable source and data required" >&2; exit 2; }
for path in scripts/tracker-qualify747.sh scripts/tracker-install747.sh \
  scripts/tracker-release-scoped747.sh scripts/tracker-release.sh; do
  bash -n "$path"
done
"$PY" -B -m py_compile \
  tests/test_release747_signed_workflows.py tests/test_release747_closeout.py
echo "RELEASE_747_SYNTAX=PASSED"
"$PY" -B -m pytest -q --tb=short --maxfail=1 \
  tests/test_release747_signed_workflows.py \
  tests/test_release747_closeout.py \
  tests/test_csrf_all_registered_negative705.py \
  tests/test_session_csrf3853.py \
  tests/test_release520_csrf_multipart.py \
  tests/test_release746_strict_water.py || exit 42
echo "RELEASE_747_ALL_REGISTERED_NEGATIVES_AND_SIGNED_POSITIVES=PASSED"
"$PY" -B -m pytest -q --tb=short --maxfail=1 \
  tests/test_release741_integrated_macd_mobile.py \
  tests/test_release738_integrated_macd_mobile.py \
  tests/test_release739_workout_food_macd_mobile.py \
  tests/test_release740_equipment_macd_mobile.py \
  tests/test_release745_macd_css.py || exit 43
echo "RELEASE_747_MACD_DATABASE_AND_MOBILE=PASSED"
"$PY" -B -m pytest -q --tb=short --maxfail=1 \
  tests/browser/test_mobile_edit_actions703.py \
  tests/browser/test_saved_food_mobile_actions702.py \
  tests/test_release746_hardening.py \
  tests/test_multiuser_audit474.py \
  tests/test_release705_dependency_readiness.py || exit 44
echo "RELEASE_747_MOBILE_MULTIUSER_DEPENDENCY=PASSED"
"$PY" -B scripts/tracker_dependency_baseline569.py --instance DEV || exit 45
echo "RELEASE_747_DEV_DEPENDENCIES=UNCHANGED_VERIFIED"
echo "RELEASE_747_FINAL_SCOPED_ACCEPTANCE=PASSED_NOT_FULL_SUITE"
