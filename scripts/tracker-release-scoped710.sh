#!/usr/bin/env bash
# Release 710: focused common dosing, blend, calendar and SQLite regressions.
# Operates only against the disposable environment of the calling release runner.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python executable required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "$TRACKER_DATA_DIR" == /tmp/* ]] ||
  { echo "Expected isolated source and disposable data" >&2; exit 2; }
bash -n scripts/tracker-release.sh
bash -n scripts/tracker_prod_remote568.sh
bash -n scripts/tracker-release-scoped710.sh
bash -n scripts/tracker-blend-vial710.sh
bash -n scripts/tracker-install710.sh
"$PY" -m py_compile app/models.py app/migrations.py app/manual_supplies.py \
  app/routers/doses.py app/blend_dose_unified710.py \
  scripts/tracker_schema_review710.py
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release710_unified_source.py \
  tests/test_release710_unified_blend_dose.py \
  tests/test_release564_blend_dose_selector.py \
  tests/test_blends.py \
  tests/test_release611_blend_calendar.py \
  tests/test_stage17_dose_blend_integrity.py \
  tests/test_dose_final_review.py \
  tests/test_dose_disposable_review.py \
  tests/test_dose_sequential_workflow.py \
  tests/test_dose_transaction_cleanup.py \
  tests/test_dose_unit_aware_supply_inputs.py \
  tests/test_dose_correction_net_inventory.py \
  tests/test_browser_qualification511.py::test_511_every_browser_module_in_disposable_qualification
echo "RELEASE_710_SCOPED_BACKEND=PASSED"
# Re-qualify the real signed HTTP+HTTPS dose flow in an independently
# disposable Chromium candidate before either DEV or PROD is changed.
bash scripts/tracker-browser-qualify.sh "$ROOT" "$PY" \
  --targeted-strict blend-vial710
echo "RELEASE_710_SCOPED_BROWSER=PASSED"
