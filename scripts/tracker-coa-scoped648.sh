#!/usr/bin/env bash
# Release 648: recover a failed PROD-only backend gate using isolated tests.
# Keep the complete existing COA/CSRF scoped gate; add source ledger contracts.
set -Eeuo pipefail
[[ "$#" == 1 && -x "$1" ]] || { echo "Expected Python executable" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && -d tests ]] || { echo "Run inside isolated candidate worktree" >&2; exit 2; }
bash "$ROOT/scripts/tracker-coa-scoped647.sh" "$PY"
"$PY" -m pytest -q --tb=short \
 tests/test_release568_ops_tooling.py \
 tests/test_release575_csrf_js_review.py \
 tests/test_release576_csrf_js_triage.py \
 tests/test_release578_csrf_route_ledger.py \
 tests/test_release579_csrf_runtime_report.py \
 tests/test_release648_prod_recovery.py
echo "COA_648_SCOPED_TESTS=PASSED"
