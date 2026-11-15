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
  tests/test_release611_blend_calendar.py \
  tests/test_release616_workflow_bundle.py \
  tests/test_release619_bundle.py \
  tests/test_release620_route_inventory.py \
  tests/test_release621_csrf_form_crosswalk.py \
  tests/test_release622_js_write_audit.py \
  tests/test_release623_csrf_review_queue.py \
  tests/test_release624_csrf_reporting_boundaries.py \
  tests/test_release625_strict_form_compat.py \
  tests/test_release626_dependency_evidence.py \
  tests/test_release626_operations_bundle.py \
  tests/test_release627_csrf_remaining_negative_matrix.py \
  tests/test_release627_csrf_reconciliation.py \
  tests/test_release627_inventory_health_filter.py \
  tests/test_release628_pk_simplified.py \
  tests/test_browser_qualification511.py \
  tests/test_release584_targeted_preflight.py \
  tests/test_release587_588_csrf_readiness.py \
  tests/test_release589_batched_qualification.py \
  tests/test_release594_food_vendor_csrf.py \
  tests/test_release597_purchase_supply_csrf.py \
  tests/test_release598_dashboard_density.py \
  tests/test_release585_dose_vial_move.py \
  tests/test_release605_oom_guard.py \
  tests/test_test_benchmark.py \
  tests/test_prod_parallel_release508.py \
  tests/test_secondary440_shard_safety503.py \
  tests/test_release603_inventory_purchase_navigation.py \
  tests/test_quick_entry_fast_paths.py \
  tests/test_long_page_navigation.py
echo "RELEASE_604_FOCUSED_PREFLIGHT=PASSED"
