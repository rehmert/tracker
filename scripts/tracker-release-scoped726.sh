#!/usr/bin/env bash
# Release 726: focused lab mobile UX and read-only overview tests.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "${TRACKER_DATA_DIR:-}" == /tmp/* ]] ||
  { echo "Release 726 requires isolated worktree/data" >&2; exit 2; }
for s in scripts/tracker-release.sh scripts/tracker-qualify726.sh \
  scripts/tracker-install726.sh scripts/tracker-release-scoped726.sh; do
  bash -n "$s"
done
"$PY" -m py_compile tests/test_release726_labs_mobile.py \
  tests/browser/test_release726_labs_mobile.py
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release726_labs_mobile.py \
  tests/test_labs_overview.py \
  tests/test_integrated_flow696.py \
  tests/browser/test_labs_overview.py \
  tests/browser/test_release726_labs_mobile.py
echo "RELEASE_726_LABS_FOCUSED=PASSED"
echo "RELEASE_726_SCOPED_QUALIFICATION=PASSED_NOT_FULL_SUITE"
