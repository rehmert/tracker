#!/usr/bin/env bash
# Release 781: changed-scope regimen ordering and MACD regression only.
set -Eeuo pipefail
umask 077
PY="${1:-}"
[[ -n "$PY" && -x "$PY" ]] || { echo "RELEASE_781_BLOCKED=Python missing" >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q --tb=short --disable-warnings \
 tests/test_release635_regimen.py \
 tests/test_release738_integrated_macd_mobile.py \
 tests/test_action_navigation675.py
echo "RELEASE_781_SCOPED=PASSED"
