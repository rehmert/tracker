#!/usr/bin/env bash
# Release 713: scoped 24-hour input and concise timeline acceptance on disposable QA.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python executable required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "${TRACKER_DATA_DIR:-}" == /tmp/* ]] ||
  { echo "Release 713 requires isolated source and disposable data" >&2; exit 2; }

for script in \
  scripts/tracker-release.sh \
  scripts/tracker-release-scoped713.sh \
  scripts/tracker-browser-qualify.sh \
  scripts/tracker-qualify713.sh \
  scripts/tracker-install713.sh \
  scripts/tracker_prod_remote568.sh; do
  bash -n "$script"
done

node --check app/static/js/tracker-time24-global713.js

"$PY" -m py_compile \
  tests/test_release713_timeline_time24.py \
  tests/browser/test_global_time24_713.py \
  tests/test_browser_qualification511.py

"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release713_timeline_time24.py \
  tests/test_release_371_time_entry.py \
  tests/test_release712_u100_withdraw_units.py \
  tests/test_release710_unified_blend_dose.py \
  tests/test_release710_unified_source.py \
  tests/test_release635_regimen.py \
  tests/test_workouts658.py \
  tests/test_pk.py \
  tests/test_dose_sequential_workflow.py \
  tests/test_browser_qualification511.py::test_511_every_browser_module_in_disposable_qualification

echo "RELEASE_713_SCOPED_BACKEND=PASSED"

bash scripts/tracker-browser-qualify.sh "$ROOT" "$PY" \
  --targeted-strict global-time24-713
echo "RELEASE_713_SCOPED_BROWSER=PASSED"
echo "RELEASE_713_SCOPED_QUALIFICATION=PASSED_NOT_FULL_SUITE"
