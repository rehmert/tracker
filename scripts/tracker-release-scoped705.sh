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
"$PY" -m py_compile \
  scripts/tracker_dependency_lock705.py \
  scripts/tracker_csrf_closeout705.py \
  tests/test_release705_combined.py
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release705_combined.py \
  tests/test_csrf_all_registered_negative705.py \
  tests/test_release569_dependency_baseline.py \
  tests/test_release570_freshenv.py \
  tests/test_release627_csrf_reconciliation.py \
  tests/test_release590_csrf_gap_plan.py \
  tests/test_release620_route_inventory.py
"$PY" -m scripts.tracker_csrf_closeout705
echo 'RELEASE_705_SOURCE_TESTS=PASSED'
echo 'RELEASE_705_ISSUE_CLOSEOUT=BLOCKED_UNTIL_RUNTIME_EVIDENCE'
echo 'RELEASE_705_SCOPED=PASSED'
