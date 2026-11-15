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
"$PY" -m pytest -n 16 --dist=loadfile -q --tb=short --maxfail=1 \
  tests/test_release_workflow.py \
  tests/test_release604_preflight.py \
  tests/test_release604_navigation_browser.py \
  tests/test_release605_vendor_label_ux.py \
  tests/test_release611_blend_calendar.py \
  tests/test_release616_workflow_bundle.py \
  tests/test_release619_bundle.py \
  tests/test_release627_inventory_health_filter.py \
  tests/test_release629_food_duplicates.py \
  tests/test_release629_required_nutrients.py \
  tests/test_release628_pk_simplified.py \
  tests/test_release629_qa_cadence.py \
  tests/test_release577_dev_receipt.py \
  tests/test_pk_278_281.py \
  tests/test_release585_dose_vial_move.py \
  tests/test_release605_oom_guard.py \
  tests/test_test_benchmark.py \
  tests/test_prod_parallel_release508.py \
  tests/test_secondary440_shard_safety503.py \
  tests/test_release603_inventory_purchase_navigation.py \
  tests/test_quick_entry_fast_paths.py \
  tests/test_long_page_navigation.py
echo "RELEASE_604_FOCUSED_PREFLIGHT=PASSED"
