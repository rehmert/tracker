#!/usr/bin/env bash
# Release 647: one COA-scoped test run, including all inherited 645/646
# contracts. Collect all failures instead of stopping on the first stale
# assertion. Uses isolated candidate test data; never the live database.
set -Eeuo pipefail
[[ "$#" == 1 && -x "$1" ]] || { echo "Expected Python executable" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && -d tests ]] || { echo "Run inside isolated candidate worktree" >&2; exit 2; }
"$PY" -m pytest -q --tb=short \
 tests/test_coa_bulk_test_types647.py \
 tests/test_coa_test_type_picker646.py \
 tests/test_coa_endotoxins645.py \
 tests/test_release_350_353.py \
 tests/test_release_354_357.py \
 tests/test_inventory_extensions.py \
 tests/test_coa_document_defaults645.py \
 tests/test_coa_multiple_documents.py \
 tests/test_coa_manager_v23.py \
 tests/test_attachment_scope396.py \
 tests/test_attachment_files400.py \
 tests/test_release572_csrf_inventory.py \
 tests/test_release573_csrf_inventory_review.py \
 tests/test_release590_csrf_gap_plan.py \
 tests/test_release591_pk_csrf_coverage.py \
 tests/test_release592_pk_compatibility.py \
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
echo "COA_647_SCOPED_TESTS=PASSED"
