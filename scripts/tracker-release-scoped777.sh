#!/usr/bin/env bash
# Release 777: changed-scope Google title save + strict CSRF + navigation regression.
set -Eeuo pipefail
umask 077
PY="${1:-}"
[[ -n "$PY" && -x "$PY" ]] || { echo "RELEASE_777_BLOCKED=Python missing" >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q --tb=short --disable-warnings \
 tests/test_release774_google_batch_titles.py \
 tests/test_csrf_form_body_report.py \
 tests/test_release520_csrf_multipart.py \
 tests/test_release773_google_custom_titles.py \
 tests/test_release776_google_tasks_focus.py \
 tests/test_release775_google_tasks_navigation.py \
 tests/test_release772_google_tasks_active_protocols.py \
 tests/test_release769_google_tasks.py
echo "RELEASE_777_SCOPED=PASSED"
