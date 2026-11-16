#!/usr/bin/env bash
# Release 653: only the Manage COA Test Types action-row layout regression.
set -Eeuo pipefail
[[ "$#" == 1 && -x "$1" ]] || { echo "Expected configured Python executable" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && -d tests ]] || { echo "Run from an isolated candidate worktree" >&2; exit 2; }
"$PY" -m pytest -q --tb=short --maxfail=1 tests/test_coa_manage_actions653.py
echo "RELEASE_653_COA_ACTION_LAYOUT=PASSED"
