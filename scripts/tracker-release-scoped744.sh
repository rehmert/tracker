#!/usr/bin/env bash
# Release 744: isolated source-only Work coordination qualification.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "$TRACKER_DATA_DIR" == /tmp/* ]] ||
  { echo "Release 744 requires isolated source and data" >&2; exit 2; }
for script in scripts/tracker-qualify744.sh scripts/tracker-install744.sh \
              scripts/tracker-release-scoped744.sh scripts/tracker-release.sh; do
  bash -n "$script"
done
"$PY" -m py_compile scripts/tracker_release_coordination744.py \
  scripts/tracker_stage_chain743.py tests/test_release744_release_coordination.py
echo "RELEASE_744_COMPILE=PASSED"
"$PY" -m pytest -q --tb=short --maxfail=1 tests/test_release744_release_coordination.py || exit 42
echo "RELEASE_744_COORDINATION_REGRESSION=PASSED"
"$PY" -m pytest -q --tb=short --maxfail=1 tests/test_release743_security_deps_chain_css.py \
  -k "stage_chain or immutable_receipts or cumulative_dev_ahead_of_prod or browser_provenance" || exit 43
echo "RELEASE_744_743_CHAIN_AND_PROVENANCE=PASSED"
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release705_combined.py \
  tests/test_release705_dependency_replay.py \
  tests/test_release705_dependency_readiness.py || exit 44
echo "RELEASE_744_SECURITY_DEPENDENCY_REGRESSION=PASSED"
echo "RELEASE_744_SCOPED_QUALIFICATION=PASSED_NOT_FULL_SUITE"
