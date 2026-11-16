#!/usr/bin/env bash
# Release 651: all COA document regression tests plus consolidated multi-types.
set -Eeuo pipefail
[[ "$#" == 1 && -x "$1" ]] || { echo "Expected configured Python executable" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && -d tests ]] || { echo "Run in isolated release worktree" >&2; exit 2; }
bash "$ROOT/scripts/tracker-coa-scoped650.sh" "$PY"
"$PY" -m pytest -q --tb=short tests/test_coa_multiple_test_types651.py
echo "COA_651_SCOPED_TESTS=PASSED"
