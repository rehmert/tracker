#!/usr/bin/env bash
# Release 782: changed-scope gym layout and logging regression only.
set -Eeuo pipefail
umask 077
PY="${1:-}"
[[ -n "$PY" && -x "$PY" ]] || { echo "RELEASE_782_BLOCKED=Python missing" >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q --tb=short --disable-warnings \
 tests/test_release782_compact_gym.py \
 tests/test_workouts659.py \
 tests/test_release725_rest_first.py \
 tests/test_action_navigation675.py \
 tests/test_integrated_mobile_ux673.py
echo "RELEASE_782_SCOPED=PASSED"
