#!/usr/bin/env bash
# Release 684: picker visibility only; no unrelated/full qualification.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python argument required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" ]] || { echo "Expected isolated source root" >&2; exit 2; }
bash -n scripts/tracker-release-scoped684.sh
bash -n scripts/tracker-preview684.sh
"$PY" -m py_compile tests/test_reconstitution_picker684.py
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_reconstitution_picker684.py \
  tests/test_reconstitution_workflow683.py \
  tests/test_reconstitution_workflow.py
echo "RELEASE_684_PICKER_VISIBILITY_QUALIFICATION=PASSED"
