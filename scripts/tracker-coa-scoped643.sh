#!/usr/bin/env bash
# Release 643 isolated change-scoped COA regression. Called only from guarded DEV worker.
set -Eeuo pipefail
[[ $# -eq 1 && -x "$1" ]] || { echo "Expected configured Python executable" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && -d "$ROOT/tests" ]] || {
 echo "Refusing to test outside isolated candidate checkout" >&2
 exit 2
}
"$PY" -m pytest -q --tb=short --maxfail=1 \
 tests/test_coa_multiple_documents.py \
 tests/test_coa_manager_v23.py \
 tests/test_coa_history_decimals_v23.py \
 tests/test_coa_migration_legacy.py \
 tests/test_attachment_scope396.py \
 tests/test_attachment_files400.py \
 tests/test_backup.py
echo "COA_643_SCOPED_TESTS=PASSED"
