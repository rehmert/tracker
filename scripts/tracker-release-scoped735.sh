#!/usr/bin/env bash
# Release 735: no application feature changes; validate six DEV releases and PROD schema gate.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "${TRACKER_DATA_DIR:-}" == /tmp/* ]] ||
  { echo "Release 735 requires isolated source/data" >&2; exit 2; }
for script in scripts/tracker-qualify735.sh scripts/tracker-install735.sh \
    scripts/tracker-release-scoped735.sh scripts/tracker-release.sh \
    scripts/tracker_prod_remote568.sh; do
  bash -n "$script"
done
"$PY" -m py_compile scripts/tracker_schema_review735.py \
  tests/test_release735_prod_catchup.py
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release735_prod_catchup.py \
  tests/test_release729_lab_entry_cards.py \
  tests/test_release730_medication_prefill.py \
  tests/test_release730_workout_page_queries.py \
  tests/test_release731_tablet_tracking.py \
  tests/test_release732_medication_delete.py \
  tests/test_release733_regimen_macd_actions.py \
  tests/test_release734_regimen_button_parity.py \
  tests/test_release636_regimen_catalog.py \
  tests/test_workouts654.py \
  tests/test_workout_dashboard661.py \
  tests/browser/test_release729_lab_entry_cards.py \
  tests/browser/test_release730_medication_prefill.py \
  tests/browser/test_release731_tablet_tracking.py
echo "RELEASE_735_CROSS_RELEASE_TESTS=PASSED"
echo "RELEASE_735_SCOPED_QUALIFICATION=PASSED_NOT_FULL_SUITE"
