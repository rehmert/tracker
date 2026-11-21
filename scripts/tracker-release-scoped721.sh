#!/usr/bin/env bash
# Release 721: focused dashboard disclosure indicator qualification.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "${TRACKER_DATA_DIR:-}" == /tmp/* ]] ||
  { echo "Release 721 requires isolated source and disposable data" >&2; exit 2; }

for script in \
  scripts/tracker-release.sh \
  scripts/tracker-release-scoped721.sh \
  scripts/tracker-qualify721.sh \
  scripts/tracker-install721.sh \
  scripts/tracker-browser-qualify.sh; do
  bash -n "$script"
done

"$PY" -m py_compile \
  tests/test_release721_recent_chevron.py \
  tests/browser/test_workout_dashboard661.py \
  tests/test_workout_dashboard661.py

"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release721_recent_chevron.py \
  tests/test_workout_dashboard661.py \
  tests/test_workout_activity_cards678.py \
  tests/test_overview_css_order682.py \
  tests/test_overview_density690.py \
  tests/browser/test_workout_dashboard661.py

echo "RELEASE_721_SCOPED_BACKEND=PASSED"
echo "RELEASE_721_SCOPED_BROWSER=PASSED"
echo "RELEASE_721_SCOPED_QUALIFICATION=PASSED_NOT_FULL_SUITE"
