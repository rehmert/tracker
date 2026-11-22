#!/usr/bin/env bash
# Release 751 scoped strict security tests (isolated data, no installed writes).
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || exit 2
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "$TRACKER_DATA_DIR" == /tmp/* ]] || exit 2
for file in scripts/tracker-qualify751.sh scripts/tracker-install751.sh \
 scripts/tracker-release-scoped751.sh scripts/tracker-csrf-dev751.sh \
 scripts/tracker-browser-qualify.sh; do
 bash -n "$file"
done
"$PY" -B -m py_compile tests/test_release751_csrf_activation.py
"$PY" -B -m pytest -q --maxfail=1 --tb=short \
 tests/test_release751_csrf_activation.py \
 tests/test_csrf_all_registered_negative705.py \
 tests/test_release520_csrf_multipart.py \
 tests/test_release521_strict_auth_compatibility.py \
 tests/test_release627_csrf_remaining_negative_matrix.py \
 tests/test_dev_attachment_gate650.py \
 tests/test_core_user_db394.py \
 tests/test_release604_preflight.py \
 tests/test_session_csrf3853.py \
 tests/test_release748_macd_mobile.py
echo "RELEASE_751_SCOPED_STRICT_CSRF=PASSED"
