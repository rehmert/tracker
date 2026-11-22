#!/usr/bin/env bash
# Release 749: portrait sidebar scoped browser and shell checks.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "$TRACKER_DATA_DIR" == /tmp/* ]] ||
  { echo "Isolated /tmp test data required" >&2; exit 2; }
for script in scripts/tracker-qualify749.sh scripts/tracker-install749.sh \
              scripts/tracker-release-scoped749.sh scripts/tracker-release.sh; do
  bash -n "$script"
done
"$PY" -B -m py_compile tests/test_release749_mobile_drawer.py
echo "RELEASE_749_SYNTAX=PASSED"
"$PY" -B -m pytest -q --tb=short --maxfail=1 \
  tests/test_release749_mobile_drawer.py \
  tests/test_mobile_app_shell507.py \
  tests/test_navigation_focus.py \
  tests/test_layout_density685.py || exit 42
echo "RELEASE_749_PORTRAIT_BROWSER_AND_SHELL=PASSED"
echo "RELEASE_749_SCOPED_QUALIFICATION=PASSED_NOT_FULL_SUITE"
