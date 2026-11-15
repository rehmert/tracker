#!/usr/bin/env bash
# Release 630: explicitly selected DEV-only targeted regressions.
# Runs on the isolated candidate worktree, never the installed application.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Expected configured Python executable" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && -d "$ROOT/tests" ]] || {
  echo "Focused 630 must run from candidate worktree" >&2
  exit 2
}
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_food_writes408.py \
  tests/test_food_review378.py \
  tests/test_food_manage377.py \
  tests/test_food_quick375.py \
  tests/test_food_quick384.py \
  tests/test_food_week379.py \
  tests/test_food_bundle376.py \
  tests/test_release629_required_nutrients.py \
  tests/test_release629_food_duplicates.py \
  tests/test_release627_csrf_reconciliation.py \
  tests/test_release627_csrf_remaining_negative_matrix.py
echo "RELEASE_630_TARGETED_QA=PASSED"
