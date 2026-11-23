#!/usr/bin/env bash
# Release 762 focused synthetic progress, existing vitals/workout, phone browser tests.
set -Eeuo pipefail
umask 077
PY="${1:-}"
[[ -n "$PY" && -x "$PY" ]] || { echo "RELEASE_762_BLOCKED=Python missing" >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q --tb=short --disable-warnings \
  tests/test_release762_progress.py \
  tests/browser/test_progress762.py \
  tests/test_vitals_range_ux.py \
  tests/test_health_insights_v23.py \
  tests/test_dashboard_forecast752.py \
  tests/test_workout_dashboard661.py
echo "RELEASE_762_SCOPED=PASSED"
