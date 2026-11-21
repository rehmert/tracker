#!/usr/bin/env bash
# Release 727 Labs cards: scoped tests; no full suite or install.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "${TRACKER_DATA_DIR:-}" == /tmp/* ]] ||
  { echo "Release 727 requires isolated source/data" >&2; exit 2; }
for s in scripts/tracker-release.sh scripts/tracker-qualify727.sh \
    scripts/tracker-install727.sh scripts/tracker-release-scoped727.sh; do bash -n "$s"; done
"$PY" -m py_compile tests/test_release727_labs_cards.py \
  tests/browser/test_release727_labs_cards.py
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release727_labs_cards.py \
  tests/test_labs_overview.py \
  tests/test_integrated_flow696.py \
  tests/test_integrated_mobile_ux673.py \
  tests/browser/test_release727_labs_cards.py \
  tests/browser/test_labs_overview.py \
  tests/browser/test_release726_labs_mobile.py
echo "RELEASE_727_LABS_CARD_TESTS=PASSED"
echo "RELEASE_727_SCOPED_QUALIFICATION=PASSED_NOT_FULL_SUITE"
