#!/usr/bin/env bash
# Release 775: Google Tasks navigation + prior Google batch-edit regression.
set -Eeuo pipefail
umask 077
PY="${1:-}"
[[ -n "$PY" && -x "$PY" ]] || { echo "RELEASE_775_BLOCKED=Python missing" >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q --tb=short --disable-warnings \
 tests/test_release775_google_tasks_navigation.py \
 tests/test_nav_preferences_v23.py \
 tests/test_navigation_productivity.py \
 tests/test_nav_titlecase.py \
 tests/test_release774_google_batch_titles.py \
 tests/test_release773_google_custom_titles.py \
 tests/test_release772_google_tasks_active_protocols.py \
 tests/test_release770_google_prod_guard.py \
 tests/test_release769_google_tasks.py
echo "RELEASE_775_SCOPED=PASSED"
