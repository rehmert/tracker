#!/usr/bin/env bash
# Release 760 change-scoped DEV qualification for PROD catch-up.
set -Eeuo pipefail
umask 077
PY="${1:-}"
[[ -n "$PY" && -x "$PY" ]] || { echo "RELEASE_760_BLOCKED=Python missing" >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q --tb=short --disable-warnings \
  tests/test_release760_prod_catchup.py \
  tests/test_release758_schema_review.py \
  tests/test_release759_mass_display.py \
  tests/test_units_calc.py \
  tests/test_dashboard_forecast752.py \
  tests/test_release756_volume_inventory_forecast.py
echo "RELEASE_760_SCOPED=PASSED"
