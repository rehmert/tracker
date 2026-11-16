#!/usr/bin/env bash
# Release 647: COA batch test-type qualification, not application-wide suite.
set -Eeuo pipefail
[[ "$#" == 1 && -x "$1" ]] || { echo "Expected Python executable" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && -d tests ]] || { echo "Run inside isolated candidate worktree" >&2; exit 2; }
"$PY" -m pytest -q --tb=short --maxfail=1 tests/test_coa_bulk_test_types647.py
bash "$ROOT/scripts/tracker-coa-scoped646.sh" "$PY"
echo "COA_647_SCOPED_TESTS=PASSED"
