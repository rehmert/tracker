#!/usr/bin/env bash
# Release 681: layout-only, focused Chromium qualification.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python argument required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" ]] || { echo "Run in isolated candidate root" >&2; exit 2; }
bash -n scripts/tracker-release-scoped681.sh
bash -n scripts/tracker-preview681.sh
"$PY" -m py_compile tests/test_workout_nav_density681.py
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_workout_nav_density681.py \
  tests/test_shortcut_buttons_browser676.py \
  tests/test_workout_activity_cards_browser678.py
echo "RELEASE_681_NAV_DENSITY_QUALIFICATION=PASSED"
