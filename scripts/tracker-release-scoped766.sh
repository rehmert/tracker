#!/usr/bin/env bash
# Release 766 combined changed-scope, no full suite or external downloads.
set -Eeuo pipefail
umask 077
PY="${1:-}"
[[ -n "$PY" && -x "$PY" ]] || { echo "RELEASE_766_BLOCKED=Python missing" >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q --tb=short --disable-warnings \
  tests/test_release766_combined.py \
  tests/browser/test_release766_mobile.py \
  tests/test_release761_missing_coa_filter.py \
  tests/test_food_bundle376.py \
  tests/test_food_manage377.py \
  tests/test_workouts659.py \
  tests/test_workouts662.py \
  tests/test_workout_offline668.py \
  tests/test_release762_progress.py \
  tests/test_mobile_daily509.py \
  tests/test_daily_flow695.py \
  tests/test_scoped_db390.py
echo "RELEASE_766_SCOPED=PASSED"
