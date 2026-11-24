#!/usr/bin/env bash
# Release 768: exact-schema immutable review, remote guard, backup/ops regressions.
set -Eeuo pipefail
umask 077
PY="${1:-}"
[[ -n "$PY" && -x "$PY" ]] || { echo "RELEASE_768_BLOCKED=Python missing" >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q --tb=short --disable-warnings \
  tests/test_release768_recovery.py \
  tests/test_release767_prod_schema_backup.py \
  tests/test_release568_ops_tooling.py \
  tests/test_release745_controller.py \
  tests/test_release705_promotion_catchup.py \
  tests/test_backup.py \
  tests/test_release766_combined.py
echo "RELEASE_768_SCOPED=PASSED"
