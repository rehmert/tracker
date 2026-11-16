#!/usr/bin/env bash
# Release 650: legacy first files and later uploads share document operations.
# Broad COA inheritance and full backend gate are prequalified on disposable data.
set -Eeuo pipefail
[[ "$#" == 1 && -x "$1" ]] || { echo "Expected Python executable" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && -d tests ]] || { echo "Run from isolated release worktree" >&2; exit 2; }
bash "$ROOT/scripts/tracker-coa-scoped649.sh" "$PY"
"$PY" -m pytest -q --tb=short \
 tests/test_coa_unified_documents650.py \
 tests/test_dev_attachment_gate650.py
echo "COA_650_SCOPED_TESTS=PASSED"
