#!/usr/bin/env bash
# Release 690: focused Overview Workout and At a glance density qualification.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python executable required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" ]] || { echo "Run inside isolated source root" >&2; exit 2; }
bash -n scripts/tracker-release-scoped690.sh
bash -n scripts/tracker-preview690.sh
"$PY" -m py_compile tests/test_overview_density690.py
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_overview_density690.py \
  tests/test_workout_footnote_spacing689.py \
  tests/test_dashboard_polish688.py \
  tests/test_workout_activity_cards_browser678.py
echo "RELEASE_690_OVERVIEW_DENSITY_QUALIFICATION=PASSED"
