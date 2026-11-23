#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
PY="$1"
[[ -n "$PY" && -x "$PY" ]] || { echo 'RELEASE_757_BLOCKED=Python required' >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q --tb=short --disable-warnings \
  tests/test_release756_calendar_vial_units.py \
  tests/test_release756_volume_inventory_forecast.py \
  tests/test_calendar_vial_handoff.py \
  tests/test_calendar_auto_vial.py \
  tests/test_forecasting.py \
  tests/test_dashboard_forecast752.py \
  tests/test_protocol_inventory_handoff.py
echo 'RELEASE_757_SCOPED=PASSED'
