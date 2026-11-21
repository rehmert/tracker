#!/usr/bin/env bash
# Release 715: scoped COA endotoxin Untested default and result preservation.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python executable required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "${TRACKER_DATA_DIR:-}" == /tmp/* ]] ||
  { echo "Release 715 requires isolated source and disposable data" >&2; exit 2; }

for script in \
  scripts/tracker-release.sh \
  scripts/tracker-release-scoped715.sh \
  scripts/tracker-browser-qualify.sh \
  scripts/tracker-qualify715.sh \
  scripts/tracker-install715.sh \
  scripts/tracker_prod_remote568.sh; do
  bash -n "$script"
done

"$PY" -m py_compile \
  app/routers/coas.py app/models.py \
  tests/test_coa_endotoxins645.py tests/test_release715_coa_untested.py \
  tests/browser/test_coa_untested715.py \
  tests/test_browser_qualification511.py

"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release715_coa_untested.py \
  tests/test_coa_endotoxins645.py \
  tests/test_coa_unified_documents650.py \
  tests/test_coa_manager_v23.py \
  tests/test_coa_multiple_test_types651.py \
  tests/test_coa_document_defaults645.py \
  tests/test_inventory_extensions.py \
  tests/test_browser_qualification511.py::test_511_every_browser_module_in_disposable_qualification

echo "RELEASE_715_SCOPED_BACKEND=PASSED"

bash scripts/tracker-browser-qualify.sh "$ROOT" "$PY" \
  --targeted-strict coa-untested715
echo "RELEASE_715_SCOPED_BROWSER=PASSED"
echo "RELEASE_715_SCOPED_QUALIFICATION=PASSED_NOT_FULL_SUITE"
