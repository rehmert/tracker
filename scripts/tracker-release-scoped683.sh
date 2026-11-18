#!/usr/bin/env bash
# Release 683: reconstitution UI, read-only calculator, and recording regressions.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python argument required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" ]] || { echo "Run inside isolated candidate root" >&2; exit 2; }
bash -n scripts/tracker-release-scoped683.sh
bash -n scripts/tracker-preview683.sh
"$PY" -m py_compile app/routers/reconstitution_calculator.py app/routers/vials.py tests/test_reconstitution_workflow683.py
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_reconstitution_workflow683.py \
  tests/test_reconstitution_workflow.py \
  tests/test_reconstitution_calculator.py
echo "RELEASE_683_RECONSTITUTION_QUALIFICATION=PASSED"
