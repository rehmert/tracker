#!/usr/bin/env bash
# Release 771: production schema/backup guard and directly affected regressions.
set -Eeuo pipefail
umask 077
PY="${1:-}"
[[ -n "$PY" && -x "$PY" ]] || { echo "RELEASE_771_BLOCKED=Python missing" >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q --tb=short --disable-warnings \
 tests/test_release771_google_prod_catchup.py \
 tests/test_release770_google_prod_guard.py \
 tests/test_release769_google_tasks.py \
 tests/test_release767_prod_schema_backup.py::test_767_signed_prod_remote_stages_guard_before_runner \
 tests/test_release767_prod_schema_backup.py::test_767_backup_refuses_every_nonprod_host_before_live_io \
 tests/test_release767_prod_schema_backup.py::test_767_backup_strict_integrity_complete_archive_and_pruning_contract \
 tests/test_release568_ops_tooling.py \
 tests/test_release705_promotion_catchup.py \
 tests/test_release745_controller.py \
 tests/test_backup.py
echo "RELEASE_771_SCOPED=PASSED"
