#!/usr/bin/env bash
# Release 769: affected app, regimen, calendar, security, and controller scope only.
set -Eeuo pipefail
umask 077
PY="${1:-}"
[[ -n "$PY" && -x "$PY" ]] || { echo "RELEASE_769_BLOCKED=Python missing" >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q --tb=short --disable-warnings  tests/test_release769_google_tasks.py  tests/test_release635_regimen.py  tests/test_release636_regimen_catalog.py  tests/test_release731_tablets.py  tests/test_scoped_db390.py  tests/test_release766_combined.py  tests/test_release745_controller.py
echo "RELEASE_769_SCOPED=PASSED"
