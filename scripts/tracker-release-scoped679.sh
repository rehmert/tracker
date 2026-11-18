#!/usr/bin/env bash
# Release 679: isolated, change-scoped UI foundation qualification.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python executable required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && -d tests ]] || { echo "Expected isolated candidate worktree" >&2; exit 2; }
bash -n scripts/tracker-release-scoped679.sh
bash -n scripts/tracker-preview679.sh
"$PY" -m py_compile tests/test_ui_foundation679.py scripts/tracker-visual-capture679.py
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_ui_foundation679.py \
  tests/test_shortcut_buttons676.py \
  tests/test_shortcut_buttons_browser676.py \
  tests/test_integrated_mobile_browser673.py
echo "RELEASE_679_UI_FOUNDATION_QUALIFICATION=PASSED"
