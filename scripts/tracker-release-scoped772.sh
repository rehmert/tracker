#!/usr/bin/env bash
# Release 772: only Google Tasks settings, projection and existing regimen/API safety.
set -Eeuo pipefail
umask 077
PY="${1:-}"
[[ -n "$PY" && -x "$PY" ]] || { echo "RELEASE_772_BLOCKED=Python missing" >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q --tb=short --disable-warnings \
 tests/test_release772_google_tasks_active_protocols.py \
 tests/test_release769_google_tasks.py \
 tests/test_release770_google_prod_guard.py \
 tests/test_release635_regimen.py
echo "RELEASE_772_SCOPED=PASSED"
