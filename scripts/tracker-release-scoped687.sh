#!/usr/bin/env bash
# Release 687: focused Daily Shortcuts density and toolbar behavior.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" ]] || { echo "Run in isolated candidate root" >&2; exit 2; }
bash -n scripts/tracker-release-scoped687.sh
bash -n scripts/tracker-preview687.sh
"$PY" -m py_compile tests/test_shortcuts_toolbar687.py
"$PY" -m pytest -q --tb=short --maxfail=1 \
 tests/test_shortcuts_toolbar687.py \
 tests/test_compact_spacing686.py \
 tests/test_layout_density685.py
echo "RELEASE_687_SHORTCUTS_TOOLBAR_QUALIFICATION=PASSED"
