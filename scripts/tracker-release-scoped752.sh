#!/usr/bin/env bash
# Release 752 scoped gate: dashboard forecast and CSRF helper.
set -Eeuo pipefail
umask 077
PY="$1"
[[ -n "$PY" && -x "$PY" ]] || { echo "RELEASE_752_BLOCKED=Python missing" >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q --tb=short --disable-warnings \
  tests/test_dashboard_forecast752.py \
  tests/test_release751_csrf_activation.py \
  tests/test_release577_dev_receipt.py
echo 'RELEASE_752_SCOPED=PASSED'
