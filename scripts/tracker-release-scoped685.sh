#!/usr/bin/env bash
# Release 685: CSS-only scoped density qualification.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Python executable required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" ]] || { echo "Run in isolated source root" >&2; exit 2; }
bash -n scripts/tracker-release-scoped685.sh
bash -n scripts/tracker-preview685.sh
"$PY" -m py_compile tests/test_layout_density685.py
"$PY" -m pytest -q --tb=short --maxfail=1 \
 tests/test_layout_density685.py \
 tests/test_ui_foundation679.py \
 tests/test_workout_nav_density681.py \
 tests/test_overview_css_order682.py
echo "RELEASE_685_LAYOUT_DENSITY_QUALIFICATION=PASSED"
