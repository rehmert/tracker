#!/usr/bin/env bash
# Release 652 mandatory focused gate. Do not inherit broad historical tests.
set -Eeuo pipefail
[[ "$#" == 1 && -x "$1" ]] || { echo "Expected qualified Python" >&2; exit 2; }
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && -d tests ]] || { echo "Use isolated source worktree" >&2; exit 2; }
bash "$ROOT/scripts/tracker-coa-scoped652.sh" "$1"
echo "RELEASE_652_SPECIFIC_TESTS=PASSED"
