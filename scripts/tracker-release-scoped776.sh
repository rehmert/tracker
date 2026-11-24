#!/usr/bin/env bash
# Release 776: everyday-navigation focus and already-verified Google titles.
set -Eeuo pipefail
umask 077
PY="${1:-}"
[[ -n "$PY" && -x "$PY" ]] || { echo "RELEASE_776_BLOCKED=Python missing" >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q --tb=short --disable-warnings \
 tests/test_release776_google_tasks_focus.py \
 tests/test_release775_google_tasks_navigation.py \
 tests/test_navigation_focus.py \
 tests/test_nav_preferences_v23.py \
 tests/test_navigation_productivity.py \
 tests/test_release774_google_batch_titles.py \
 tests/test_release773_google_custom_titles.py \
 tests/test_release772_google_tasks_active_protocols.py
echo "RELEASE_776_SCOPED=PASSED"
