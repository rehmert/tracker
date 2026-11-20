#!/usr/bin/env bash
# Release 712: scoped QA for U-100 syringe units as physical withdrawal volume.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python executable required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "${TRACKER_DATA_DIR:-}" == /tmp/* ]] ||
  { echo "Release 712 requires isolated source and disposable data" >&2; exit 2; }

for script in \
  scripts/tracker-release.sh \
  scripts/tracker-release-scoped712.sh \
  scripts/tracker-browser-qualify.sh \
  scripts/tracker-qualify712.sh \
  scripts/tracker-install712.sh \
  scripts/tracker_prod_remote568.sh; do
  bash -n "$script"
done

"$PY" -m py_compile \
  app/units.py app/templating.py app/routers/doses.py \
  app/blend_dose_unified710.py \
  tests/test_release712_u100_withdraw_units.py \
  tests/browser/test_u100_withdraw712.py \
  tests/test_browser_qualification511.py

"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release712_u100_withdraw_units.py \
  tests/test_units_calc.py \
  tests/test_release710_unified_blend_dose.py \
  tests/test_release710_unified_source.py \
  tests/test_release711_blend_dose_corrections.py \
  tests/test_release711_source_contracts.py \
  tests/test_dose_audit_v23.py \
  tests/test_dose_correction_net_inventory.py \
  tests/test_dose_correction_page.py \
  tests/test_dose_disposable_review.py \
  tests/test_dose_transaction_cleanup.py \
  tests/test_dose_unit_aware_supply_inputs.py \
  tests/test_stage17_dose_blend_integrity.py \
  tests/test_browser_qualification511.py::test_511_every_browser_module_in_disposable_qualification

echo "RELEASE_712_SCOPED_BACKEND=PASSED"

bash scripts/tracker-browser-qualify.sh "$ROOT" "$PY" \
  --targeted-strict u100-withdraw712
echo "RELEASE_712_SCOPED_BROWSER=PASSED"
echo "RELEASE_712_SCOPED_QUALIFICATION=PASSED_NOT_FULL_SUITE"
