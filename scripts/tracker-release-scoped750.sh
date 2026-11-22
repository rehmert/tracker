#!/usr/bin/env bash
# Release 750: isolated real account switching + browser-copy recovery checks.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || exit 2
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "$TRACKER_DATA_DIR" == /tmp/* ]] || exit 2
for f in scripts/tracker-qualify750.sh scripts/tracker-install750.sh \
         scripts/tracker-release-scoped750.sh; do bash -n "$f"; done
"$PY" -B -m py_compile scripts/tracker_browser_restore750.py tests/test_release750_acceptance.py
"$PY" -B -m pytest -q --maxfail=1 --tb=short \
 tests/test_release750_acceptance.py \
 tests/test_secondary_private_workflow440.py \
 tests/test_unified_login473.py \
 tests/test_workspace_isolation399.py \
 tests/test_release748_host_evidence.py \
 tests/test_release705_dependency_replay.py || exit 42
echo "RELEASE_750_MULTIUSER_PILOT_ACCOUNT_ACCEPTANCE=PASSED"
"$PY" -B scripts/tracker_browser_restore750.py --disposable-replay || exit 43
echo "RELEASE_750_SCOPED_ACCEPTANCE=PASSED_NOT_FULL_SUITE"
