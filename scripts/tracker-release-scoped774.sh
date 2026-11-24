#!/usr/bin/env bash
# Release 774: changed-scope Google Tasks batch edit plus prior sync/regimen regressions.
set -Eeuo pipefail
umask 077
PY="${1:-}"
[[ -n "$PY" && -x "$PY" ]] || { echo "RELEASE_774_BLOCKED=Python missing" >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q --tb=short --disable-warnings \
 tests/test_release774_google_batch_titles.py \
 tests/test_release773_google_custom_titles.py \
 tests/test_release769_google_tasks.py \
 tests/test_release770_google_prod_guard.py \
 tests/test_release772_google_tasks_active_protocols.py \
 tests/test_release635_regimen.py
echo "RELEASE_774_SCOPED=PASSED"
