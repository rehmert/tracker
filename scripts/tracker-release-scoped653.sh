#!/usr/bin/env bash
# Release 653: only Manage COA Test Types action-row layout regression.
# DEV verifies real Chromium geometry; PROD runs the same rendered-HTML
# contract without assuming Chromium is installed on the production server.
set -Eeuo pipefail
[[ "$#" == 1 || ( "$#" == 2 && "$2" == --prod ) ]] ||
  { echo "Usage: $0 PYTHON [--prod]" >&2; exit 2; }
[[ -x "$1" ]] || { echo "Expected configured Python executable" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && -d tests ]] ||
  { echo "Run from isolated candidate worktree" >&2; exit 2; }
if [[ "${2:-}" == --prod ]]; then
  "$PY" -m pytest -q --tb=short --maxfail=1 \
    tests/test_coa_manage_actions653.py::test_653_manage_action_markup_and_css_contract \
    tests/test_tracker_instance_check653.py
  echo "RELEASE_653_PROD_MARKUP_CONTRACT=PASSED"
else
  "$PY" -m pytest -q --tb=short --maxfail=1 \
    tests/test_coa_manage_actions653.py \
    tests/test_tracker_instance_check653.py
  echo "RELEASE_653_CHROMIUM_LAYOUT=PASSED"
fi
echo "RELEASE_653_COA_ACTION_LAYOUT=PASSED"
