#!/usr/bin/env bash
# Release 759 focused tests: mass display, inventory forecasts and template contracts.
set -Eeuo pipefail
umask 077
PY="${1:-}"
[[ -n "$PY" && -x "$PY" ]] || { echo 'RELEASE_759_BLOCKED=Python missing' >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q --tb=short --disable-warnings \
  tests/test_release759_mass_display.py \
  tests/test_units_calc.py \
  tests/test_dashboard_forecast752.py \
  tests/test_release756_volume_inventory_forecast.py \
  tests/test_vial_inventory_reports.py \
  tests/test_forecasting.py
echo 'RELEASE_759_SCOPED=PASSED'
