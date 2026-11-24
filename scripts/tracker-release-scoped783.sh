#!/usr/bin/env bash
# Release 783: Google protocol review, calendar, vitals and scoped DB regression.
set -Eeuo pipefail
umask 077
PY="${1:-}"
[[ -n "$PY" && -x "$PY" ]] || { echo "RELEASE_783_BLOCKED=Python missing" >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q --tb=short --disable-warnings \
 tests/test_release783_reconciliation.py \
 tests/test_release780_google_completion_poll.py \
 tests/test_release769_google_tasks.py \
 tests/test_release770_google_prod_guard.py \
 tests/test_release772_google_tasks_active_protocols.py \
 tests/test_release773_google_custom_titles.py \
 tests/test_release774_google_batch_titles.py \
 tests/test_calendar_workbench.py \
 tests/test_calendar_review_agenda.py \
 tests/test_calendar_sort668.py \
 tests/test_vitals_date_review.py \
 tests/test_vitals_range_ux.py \
 tests/test_core_user_db394.py
echo "RELEASE_783_SCOPED=PASSED"
