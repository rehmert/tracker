#!/usr/bin/env bash
# Release 682: CSS source-order correction and relevant browser regressions only.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Python argument required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" ]] || { echo "Must run in isolated source root" >&2; exit 2; }
bash -n scripts/tracker-release-scoped682.sh
bash -n scripts/tracker-preview682.sh
"$PY" -m py_compile tests/test_overview_css_order682.py
"$PY" -m pytest -q --tb=short --maxfail=1 \
 tests/test_overview_css_order682.py \
 tests/test_workout_nav_density681.py \
 tests/test_workout_activity_cards_browser678.py
echo "RELEASE_682_OVERVIEW_CSS_ORDER_QUALIFICATION=PASSED"
