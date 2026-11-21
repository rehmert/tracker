#!/usr/bin/env bash
# Release 722: focused, executable workout phone flow and markup tests.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "${TRACKER_DATA_DIR:-}" == /tmp/* ]] ||
  { echo "Release 722 requires isolated source and disposable data" >&2; exit 2; }

for file in scripts/tracker-qualify722.sh scripts/tracker-install722.sh \
    scripts/tracker-release-scoped722.sh scripts/tracker-release.sh \
    scripts/tracker-browser-qualify.sh; do
  bash -n "$file"
done
"$PY" -m py_compile tests/test_release722_gym_focus.py \
    tests/browser/test_workout_active716.py tests/browser/test_workout_manage719.py
"$PY" -m pytest -q --tb=short --maxfail=1 \
    tests/test_release722_gym_focus.py \
    tests/test_workouts659.py \
    tests/test_release720_inline_delete.py \
    tests/test_release717_completed_edit.py
echo "RELEASE_722_SCOPED_BACKEND=PASSED"

# Strict, signed HTTP and HTTPS Chromium on disposable private data.
bash scripts/tracker-browser-qualify.sh "$ROOT" "$PY" \
    --targeted-strict workout-active716
bash scripts/tracker-browser-qualify.sh "$ROOT" "$PY" \
    --targeted-strict workout-manage719
echo "RELEASE_722_SCOPED_BROWSER=PASSED"
echo "RELEASE_722_SCOPED_QUALIFICATION=PASSED_NOT_FULL_SUITE"
