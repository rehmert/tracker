#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
PY="$1"
[[ -n "$PY" && -x "$PY" ]] || { echo 'RELEASE_755_BLOCKED=Python missing' >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q --tb=short --disable-warnings \
  tests/test_release754_progress_export.py \
  tests/test_release755_clinical_export.py
echo 'RELEASE_755_SCOPED=PASSED'
