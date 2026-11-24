#!/usr/bin/env bash
# Release 764 focused compound-title and navigation regressions.
set -Eeuo pipefail
umask 077
PY="${1:-}"
[[ -n "$PY" && -x "$PY" ]] || { echo 'RELEASE_764_BLOCKED=Python missing' >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q --tb=short --disable-warnings \
  tests/test_release764_compound_title_case.py \
  tests/test_page_title_case.py \
  tests/test_nav_titlecase.py \
  tests/test_release599_dashboard_polish.py
echo 'RELEASE_764_SCOPED=PASSED'
