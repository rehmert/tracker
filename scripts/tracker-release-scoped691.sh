#!/usr/bin/env bash
# Release 691: focused COA document identifier, migration, and adjacent workflow QA.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python executable required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" ]] || { echo "Run inside isolated source root" >&2; exit 2; }
bash -n scripts/tracker-release.sh
bash -n scripts/tracker-release-scoped691.sh
bash -n scripts/tracker-preview691.sh
"$PY" -m py_compile \
  app/models.py app/migrations.py app/routers/coas.py \
  scripts/tracker_schema_review691.py tests/test_coa_document_identifiers691.py
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_coa_document_identifiers691.py \
  tests/test_coa_multiple_documents.py \
  tests/test_coa_unified_documents650.py \
  tests/test_coa_documents_ui649.py \
  tests/test_coa_multiple_test_types651.py \
  tests/test_coa_bulk_test_types647.py \
  tests/test_coa_manager_v23.py \
  tests/test_coa_document_defaults645.py \
  tests/test_coa_manage_catalog652.py
echo "RELEASE_691_COA_DOCUMENT_IDENTIFIERS_QUALIFICATION=PASSED"
