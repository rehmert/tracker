#!/usr/bin/env bash
# Release 784: vitals pagination, notes and browser regression only.
set -Eeuo pipefail
umask 077
PY="${1:-}"
[[ -n "$PY" && -x "$PY" ]] || { echo "RELEASE_784_BLOCKED=Python missing" >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT" PYTHONDONTWRITEBYTECODE=1
"$PY" -B -m pytest -q --tb=short --disable-warnings \
 tests/test_vitals_date_review.py \
 tests/test_vitals_range_ux.py \
 tests/test_release783_reconciliation.py::test_783_vitals_edit_actions_and_full_note_contract \
 tests/test_vitals_csv_browser.py
echo "RELEASE_784_SCOPED=PASSED"
