#!/usr/bin/env bash
# Release 688: change-scoped Dashboard polish and relevant existing regressions.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python executable required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" ]] || { echo "Run inside isolated source root" >&2; exit 2; }
bash -n scripts/tracker-release-scoped688.sh
bash -n scripts/tracker-preview688.sh
"$PY" -m py_compile tests/test_dashboard_polish688.py tests/test_workout_activity_cards_browser678.py
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_dashboard_polish688.py \
  tests/test_workout_activity_cards_browser678.py \
  tests/test_shortcuts_toolbar687.py \
  tests/test_compact_spacing686.py \
  tests/test_section_deep_links.py \
  tests/test_long_page_navigation.py \
  tests/browser/test_workout_dashboard661.py
echo "RELEASE_688_DASHBOARD_POLISH_QUALIFICATION=PASSED"
