#!/usr/bin/env bash
# Release 753: UI-only scoped tests including desktop/mobile browser geometry.
set -Eeuo pipefail
umask 077
PY="$1"
[[ -n "$PY" && -x "$PY" ]] || { echo "RELEASE_753_BLOCKED=Python missing" >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q --tb=short --disable-warnings \
  tests/test_release753_list_density.py \
  tests/test_integrated_flow696.py \
  tests/test_integrated_mobile_ux673.py \
  tests/test_release746_hardening.py \
  tests/test_release741_integrated_macd_mobile.py
echo 'RELEASE_753_SCOPED=PASSED'
