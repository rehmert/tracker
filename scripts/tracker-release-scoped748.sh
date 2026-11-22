#!/usr/bin/env bash
# Release 748 combined #54 #56 #10, scoped isolated DEV source qualification.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "$TRACKER_DATA_DIR" == /tmp/* ]] ||
  { echo "Private /tmp candidate data required" >&2; exit 2; }
for script in scripts/tracker-qualify748.sh scripts/tracker-install748.sh \
              scripts/tracker-release-scoped748.sh scripts/tracker-release.sh; do
  bash -n "$script"
done
"$PY" -B -m py_compile scripts/tracker_browser_elf748.py \
  tests/test_release748_host_evidence.py tests/test_release748_macd_mobile.py
echo "RELEASE_748_SYNTAX=PASSED"
"$PY" -B -m pytest -q --tb=short --maxfail=1 \
  tests/test_release748_host_evidence.py \
  tests/test_release748_macd_mobile.py \
  tests/test_release747_signed_workflows.py \
  tests/test_release746_strict_water.py || exit 42
echo "RELEASE_748_ELF_SIGNED_MACD_NOTES_LABS=PASSED"
"$PY" -B -m pytest -q --tb=short --maxfail=1 \
  tests/test_release741_integrated_macd_mobile.py \
  tests/test_release738_integrated_macd_mobile.py \
  tests/test_release739_workout_food_macd_mobile.py \
  tests/test_release740_equipment_macd_mobile.py \
  tests/test_release745_macd_css.py || exit 43
echo "RELEASE_748_HISTORICAL_OWNER_SCOPED_MACD=PASSED"
"$PY" -B -m pytest -q --tb=short --maxfail=1 \
  tests/browser/test_mobile_edit_actions703.py \
  tests/browser/test_saved_food_mobile_actions702.py \
  tests/test_release746_hardening.py \
  tests/test_multiuser_audit474.py \
  tests/test_release705_dependency_readiness.py || exit 44
echo "RELEASE_748_RESPONSIVE_MULTIUSER_DEPENDENCY=PASSED"
"$PY" -B scripts/tracker_dependency_baseline569.py --instance DEV || exit 45
echo "RELEASE_748_INSTALLED_DEV_PYTHON=BASELINE_VERIFIED"
"$PY" -B scripts/tracker_browser_elf748.py --capture \
  --output "$TRACKER_DATA_DIR/chromium-elf748.json" || exit 46
echo "RELEASE_748_INSTALLED_DEV_CHROMIUM_ELF=HASHED_NO_ROLLBACK_CLAIM"
echo "RELEASE_748_SCOPED_QUALIFICATION=PASSED_NOT_FULL_SUITE"
