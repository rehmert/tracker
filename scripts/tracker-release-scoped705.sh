#!/usr/bin/env bash
# Release 705: one source qualification for both unresolved issues.
# No live service, DB, dependency install or CSRF flag changes.
set -Eeuo pipefail

[[ "$#" == 1 && -x "$1" ]] || {
  echo 'Usage: tracker-release-scoped705.sh CONFIGURED_PYTHON' >&2
  exit 2
}
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "$ROOT" != /opt/tracker ]] || {
  echo 'Release 705 requires an isolated detached candidate worktree' >&2
  exit 2
}
bash -n scripts/tracker-release-scoped705.sh
bash -n scripts/tracker-preview705.sh
bash -n scripts/tracker-browser-preview705.sh
bash -n scripts/tracker-dependency-preview705.sh
bash -n scripts/tracker-dependency-acquire705.sh
bash -n scripts/tracker-dependency-replay705.sh
"$PY" -m py_compile \
  scripts/tracker_dependency_lock705.py \
  scripts/tracker_dependency_readiness705.py \
  scripts/tracker_dependency_acquire705.py \
  scripts/tracker_dependency_replay705.py \
  scripts/tracker_promote568.py \
  tests/test_release705_promotion_catchup.py \
  tests/test_release705_dependency_replay.py \
  tests/test_release705_dependency_acquire.py \
  tests/test_release705_dependency_readiness.py \
  scripts/tracker_csrf_closeout705.py \
  scripts/tracker_csrf_reconcile627.py \
  tests/test_release627_csrf_reconciliation.py \
  scripts/tracker_csrf_runtime_report579.py \
  tests/test_release579_csrf_runtime_report.py \
  tests/test_release575_csrf_js_review.py \
  tests/test_release576_csrf_js_triage.py \
  tests/test_release578_csrf_route_ledger.py \
  tests/test_release640_csrf_inventory.py \
  tests/test_release648_prod_recovery.py \
  tests/test_coa_multiple_test_types651.py \
  tests/test_release705_combined.py \
  tests/test_csrf_all_registered_negative705.py \
  tests/browser/test_vitals_proxy_host522.py \
  tests/browser/test_strict_csrf521.py \
  tests/browser/test_csrf_workflows580.py \
  tests/browser/test_csrf_preparations583.py
# Reconcile every historical source/ledger test that pinned 50 -> 51
# before any expensive HTTP/HTTPS browser qualification.
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release575_csrf_js_review.py \
  tests/test_release576_csrf_js_triage.py \
  tests/test_release578_csrf_route_ledger.py \
  tests/test_release579_csrf_runtime_report.py \
  tests/test_release640_csrf_inventory.py \
  tests/test_release648_prod_recovery.py::test_648_historical_csrf_witnesses_stay_unqualified \
  tests/test_coa_multiple_test_types651.py::test_651_new_ajax_callsite_is_inventory_reviewed_but_not_historically_cleared
echo 'RELEASE_705_51_TRACKED_JS_SOURCE_LEDGER=PASSED'

# Release 705 read-only offline wheel and installed-baseline readiness
# contracts must pass before ASGI or browser tests; no wheelhouse required.
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release705_dependency_readiness.py
echo 'DEPENDENCY_705_SOURCE_READINESS_CONTRACT=PASSED'

# Validate download-only CLI shape, PyPI digest/host/yank matching, and
# no-install environment guarantees before any browser or ASGI tests.
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release705_dependency_acquire.py
echo 'DEPENDENCY_705_ACQUIRE_SOURCE_CONTRACT=PASSED'

# Offline-only source contracts: require exact hashes, fully independent
# two-pass venvs, PrivateNetwork namespace, no index or browser downloads.
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release705_dependency_replay.py
echo 'DEPENDENCY_705_OFFLINE_REPLAY_SOURCE_CONTRACT=PASSED'

# Release 705 signed DEV->PROD catch-up must remain narrowly restricted
# to an already-reviewed Release 693+ PROD base and exact Release 704 main.
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release568_ops_tooling.py \
  tests/test_release705_promotion_catchup.py
echo 'RELEASE_705_SIGNED_PROMOTION_CATCHUP_CONTRACT=PASSED'

# Check the exact-commit runtime runner contract before any ASGI requests.
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release705_runtime_preview.py
echo 'RELEASE_705_BROWSER_RUNNER_CONTRACT=PASSED'

# Check the read-only browser gate inventory FIRST; failure before ASGI.
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_browser_qualification511.py::test_511_every_browser_module_in_disposable_qualification
echo 'RELEASE_705_BROWSER_MODULE_INVENTORY=PASSED'

# ASGI negative matrix next, before broader historical source regressions.
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_csrf_all_registered_negative705.py
echo 'RELEASE_705_ASGI_CSRF_NEGATIVE_CANARY=PASSED'

# A Release 627 source baseline count cannot stay frozen after 38 new
# Release 654..704 unsafe routes. Check exact source reconciliation first;
# unexpected additions/removals still block, rather than masking evidence.
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release627_csrf_reconciliation.py \
  -k 'signed_route_reconciliation_stays_blocked or signed_route_manifest_has_no_duplicate_or_unmapped_routes'
echo 'RELEASE_705_HISTORICAL_CSRF_RECONCILIATION=PASSED'

"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release705_combined.py \
  tests/test_release569_dependency_baseline.py \
  tests/test_release570_freshenv.py \
  tests/test_release627_csrf_reconciliation.py \
  tests/test_release590_csrf_gap_plan.py \
  tests/test_release620_route_inventory.py
"$PY" -m scripts.tracker_csrf_closeout705
echo 'RELEASE_705_SOURCE_TESTS=PASSED'
echo 'RELEASE_705_ISSUE_CLOSEOUT=BLOCKED_UNTIL_RUNTIME_EVIDENCE'
echo 'RELEASE_705_SCOPED=PASSED'
