#!/usr/bin/env bash
# Release 770: focused Google Tasks DEV-denial, existing mock sync and affected regressions.
set -Eeuo pipefail
umask 077
PY="${1:-}"
[[ -n "$PY" && -x "$PY" ]] || { echo "RELEASE_770_BLOCKED=Python missing" >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q --tb=short --disable-warnings \
 tests/test_release770_google_prod_guard.py \
 tests/test_release769_google_tasks.py \
 tests/test_release635_regimen.py \
 tests/test_release731_tablet_tracking.py \
 tests/test_scoped_db390.py \
 tests/test_release745_controller.py
echo "RELEASE_770_SCOPED=PASSED"
