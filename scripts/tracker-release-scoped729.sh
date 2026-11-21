#!/usr/bin/env bash
# Release 729: change-scoped manual Labs mobile QA, no full suite or install.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "$TRACKER_DATA_DIR" == /tmp/* ]] ||
  { echo "Release 729 requires isolated source/data" >&2; exit 2; }
for s in scripts/tracker-release.sh scripts/tracker-qualify729.sh \
    scripts/tracker-install729.sh scripts/tracker-release-scoped729.sh; do
  bash -n "$s"
done
"$PY" -m py_compile tests/test_release729_lab_entry_cards.py \
  tests/browser/test_release729_lab_entry_cards.py
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release729_lab_entry_cards.py \
  tests/test_lab_entry_review_ux.py \
  tests/test_lab_entry_safeguards.py \
  tests/test_lab_review_navigation.py \
  tests/test_lab_source_picker.py \
  tests/test_lab_csv_import.py \
  tests/test_consolidated_forms704.py \
  tests/test_integrated_mobile_ux673.py \
  tests/browser/test_release729_lab_entry_cards.py \
  tests/browser/test_consolidated_forms704.py
echo "RELEASE_729_LAB_ENTRY_CARD_TESTS=PASSED"
echo "RELEASE_729_SCOPED_QUALIFICATION=PASSED_NOT_FULL_SUITE"
