#!/usr/bin/env bash
# Release 779: universal compact 24h time entry and impacted forms, scoped QA.
set -Eeuo pipefail
umask 077
PY="${1:-}"
[[ -n "$PY" && -x "$PY" ]] || { echo "RELEASE_779_BLOCKED=Python missing" >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q --tb=short --disable-warnings \
 tests/test_release779_compact_time.py \
 tests/test_release_371_time_entry.py \
 tests/test_release713_timeline_time24.py \
 tests/test_release_370_time_display.py \
 tests/test_release778_regimen_return.py \
 tests/test_release635_regimen.py \
 tests/test_release738_integrated_macd_mobile.py
echo "RELEASE_779_SCOPED=PASSED"
