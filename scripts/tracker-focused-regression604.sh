#!/usr/bin/env bash
# Release 604: isolated, focused DEV preflight; never deploys.
# Kept separate from tracker-release.sh to preserve the unique complete-suite
# pytest invocation checked by tests/test_release_workflow.py.
set -Eeuo pipefail
[[ "$#" == 1 && -x "$1" ]] || {
  echo "ERROR: Expected configured Python executable" >&2
  exit 2
}
PY="$1"
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && -d "$ROOT/tests" ]] || {
  echo "ERROR: Run in isolated candidate worktree" >&2
  exit 2
}
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release_workflow.py \
  tests/test_release604_preflight.py \
  tests/test_release604_navigation_browser.py \
  tests/test_release605_vendor_label_ux.py \
  tests/test_release605_oom_guard.py \
  tests/test_test_benchmark.py \
  tests/test_prod_parallel_release508.py \
  tests/test_secondary440_shard_safety503.py \
  tests/test_release603_inventory_purchase_navigation.py \
  tests/test_quick_entry_fast_paths.py \
  tests/test_long_page_navigation.py
echo "RELEASE_604_FOCUSED_PREFLIGHT=PASSED"
