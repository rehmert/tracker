#!/usr/bin/env bash
# Release 761 focused dashboard/vial-COA filter qualification.
set -Eeuo pipefail
umask 077
PY="${1:-}"
[[ -n "$PY" && -x "$PY" ]] || { echo "RELEASE_761_BLOCKED=Python missing" >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q --tb=short --disable-warnings \
  tests/test_release761_missing_coa_filter.py \
  tests/test_vial_inventory_reports.py \
  tests/test_release603_inventory_purchase_navigation.py::test_603_vials_retain_all_bulk_tools_and_jump_open_sections \
  tests/test_dashboard_forecast752.py \
  tests/test_release759_mass_display.py \
  tests/test_release4_inventory.py
echo "RELEASE_761_SCOPED=PASSED"
