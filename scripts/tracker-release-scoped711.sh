#!/usr/bin/env bash
# Release 711: exact change-scoped, disposable correction and existing dose QA.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python executable required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "${TRACKER_DATA_DIR:-}" == /tmp/* ]] ||
  { echo "Release 711 requires isolated source and disposable data" >&2; exit 2; }

for script in \
  scripts/tracker-release.sh \
  scripts/tracker-release-scoped711.sh \
  scripts/tracker-browser-qualify.sh \
  scripts/tracker-qualify711.sh \
  scripts/tracker-install711.sh \
  scripts/tracker_prod_remote568.sh; do
  bash -n "$script"
done
"$PY" -m py_compile app/routers/doses.py app/routers/blends.py \
  app/blend_dose_identity711.py app/manual_supplies.py \
  tests/test_release711_blend_dose_corrections.py \
  tests/browser/test_blend_corrections711.py

"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release711_blend_dose_corrections.py \
  tests/test_release711_source_contracts.py \
  tests/test_release710_unified_blend_dose.py \
  tests/test_release710_unified_source.py \
  tests/test_blends.py \
  tests/test_release611_blend_calendar.py \
  tests/test_dose_audit_v23.py \
  tests/test_dose_correction_net_inventory.py \
  tests/test_dose_correction_page.py \
  tests/test_dose_disposable_review.py \
  tests/test_dose_transaction_cleanup.py \
  tests/test_dose_unit_aware_supply_inputs.py \
  tests/test_stage17_dose_blend_integrity.py \
  tests/test_browser_qualification511.py::test_511_every_browser_module_in_disposable_qualification
echo "RELEASE_711_SCOPED_BACKEND=PASSED"

bash scripts/tracker-browser-qualify.sh "$ROOT" "$PY" \
  --targeted-strict blend-correction711
echo "RELEASE_711_SCOPED_BROWSER=PASSED"
echo "RELEASE_711_SCOPED_QUALIFICATION=PASSED_NOT_FULL_SUITE"
