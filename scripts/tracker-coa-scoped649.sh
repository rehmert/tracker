#!/usr/bin/env bash
# Release 649: isolated COA UI regression chain, not the full application suite.
set -Eeuo pipefail
[[ "$#" == 1 && -x "$1" ]] || { echo "Expected configured Python executable" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && -d tests ]] || { echo "Must run inside disposable release worktree" >&2; exit 2; }
bash "$ROOT/scripts/tracker-coa-scoped647.sh" "$PY"
"$PY" -m pytest -q --tb=short \
 tests/test_coa_documents_ui649.py \
 tests/test_release575_csrf_js_review.py \
 tests/test_release576_csrf_js_triage.py \
 tests/test_release578_csrf_route_ledger.py \
 tests/test_release579_csrf_runtime_report.py \
 tests/test_release640_csrf_inventory.py \
 tests/test_release648_prod_recovery.py \
 tests/test_release568_ops_tooling.py
echo "COA_649_SCOPED_TESTS=PASSED"
