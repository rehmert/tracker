#!/usr/bin/env bash
# Isolated Release 645 COA default-file focused QA. Not the full suite.
set -Eeuo pipefail
[[ "$#" == 1 && -x "$1" ]] || { echo "Expected configured Python binary" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && -d "$ROOT/tests" ]] || {
 echo "Must run from isolated candidate worktree" >&2
 exit 2
}
"$PY" -m pytest -q --tb=short --maxfail=1 \
 tests/test_coa_endotoxins645.py \
 tests/test_coa_document_defaults645.py \
 tests/test_coa_multiple_documents.py \
 tests/test_coa_manager_v23.py \
 tests/test_attachment_scope396.py \
 tests/test_attachment_files400.py \
 tests/test_release627_csrf_remaining_negative_matrix.py \
 tests/test_release627_csrf_reconciliation.py \
 tests/test_release597_purchase_supply_csrf.py \
 tests/test_release574_csrf_dynamic_shapes.py \
 tests/test_release574_csrf_multipart_matrix.py \
 tests/test_release596_vendor_multipart_csv.py \
 tests/test_release593_pk_final_witnesses.py \
 tests/test_release594_food_vendor_csrf.py \
 tests/test_release595_food_vendor_lifecycle.py \
 tests/test_backup.py
echo "COA_645_SCOPED_TESTS=PASSED"
