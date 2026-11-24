#!/usr/bin/env bash
# Release 765: changed-scope mobile Today and exact-record dashboard actions.
set -Eeuo pipefail
umask 077
PY="${1:-}"
[[ -n "$PY" && -x "$PY" ]] || { echo 'RELEASE_765_BLOCKED=Python missing' >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q --tb=short --disable-warnings \
  tests/test_release765_daily_actions.py \
  tests/test_mobile_daily509.py \
  tests/test_daily_flow695.py \
  tests/test_release761_missing_coa_filter.py \
  tests/test_dashboard_dose_shortcuts.py \
  tests/test_today_dashboard.py
echo 'RELEASE_765_SCOPED=PASSED'
