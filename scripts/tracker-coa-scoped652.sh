#!/usr/bin/env bash
# Release 652: COA-only compatibility and managed catalog regression gate.
set -Eeuo pipefail
[[ "$#" == 1 && -x "$1" ]] || { echo "Expected configured Python executable" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && -d tests ]] || { echo "Run from a qualified isolated release worktree" >&2; exit 2; }
bash "$ROOT/scripts/tracker-coa-scoped651.sh" "$PY"
"$PY" -m pytest -q --tb=short tests/test_coa_manage_catalog652.py
echo "COA_652_SCOPED_TESTS=PASSED"
