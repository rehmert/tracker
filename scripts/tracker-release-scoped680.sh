#!/usr/bin/env bash
# Release 680: focused browser behavior and existing explanation contracts only.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && -d tests ]] || { echo "Expected isolated candidate" >&2; exit 2; }
bash -n scripts/tracker-release-scoped680.sh
bash -n scripts/tracker-preview680.sh
"$PY" -m py_compile tests/test_explanation_touch680.py
"$PY" -m pytest -q --tb=short --maxfail=1 \
 tests/test_explanation_touch680.py \
 tests/test_shortcut_buttons676.py \
 tests/test_shortcut_buttons_browser676.py
echo "RELEASE_680_EXPLANATION_TOUCH_QUALIFICATION=PASSED"
