#!/usr/bin/env bash
# Release 652: COA-only compatibility and managed catalog regression gate.
set -Eeuo pipefail
[[ "$#" == 1 && -x "$1" ]] || { echo "Expected configured Python executable" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && -d tests ]] || { echo "Run from a qualified isolated release worktree" >&2; exit 2; }
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_coa_manage_catalog652.py \
  tests/test_coa_backup652.py \
  tests/test_release629_qa_cadence.py::test_652_full_regression_requires_explicit_operator_opt_in \
  tests/test_release577_dev_receipt.py::test_652_scoped_only_dev_receipt_is_accepted_without_broad_604_gate \
  tests/test_coa_multiple_test_types651.py::test_651_stable_codebook_and_unmodified_legacy_labels \
  tests/test_coa_multiple_test_types651.py::test_651_multiple_types_persist_in_one_file_without_changing_default \
  tests/test_coa_multiple_test_types651.py::test_651_atomic_stale_duplicate_and_cross_record_rejection \
  tests/test_coa_multiple_test_types651.py::test_651_legacy_first_file_can_have_multiple_tests_without_duplicate_pdf \
  tests/test_coa_multiple_test_types651.py::test_651_combined_types_upload_and_custom_type_persist \
  tests/test_coa_test_type_picker646.py::test_646_compact_picker_renders_groups_and_preserves_unknown_historical_label
echo "COA_652_SCOPED_TESTS=PASSED"
