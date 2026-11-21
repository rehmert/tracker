#!/usr/bin/env bash
# Release 720: focused compact inline workout deletion UI checks.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "${TRACKER_DATA_DIR:-}" == /tmp/* ]] ||
  { echo "Release 720 requires isolated worktree and temporary DB" >&2; exit 2; }

for script in \
  scripts/tracker-release.sh \
  scripts/tracker-release-scoped720.sh \
  scripts/tracker-qualify720.sh \
  scripts/tracker-install720.sh \
  scripts/tracker-browser-qualify.sh \
  scripts/tracker_prod_remote568.sh; do
  bash -n "$script"
done

"$PY" -m py_compile \
  tests/test_release720_inline_delete.py \
  tests/test_release719_workout_history.py \
  tests/browser/test_workout_manage719.py

"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release720_inline_delete.py \
  tests/test_release719_workout_history.py \
  tests/test_release717_completed_edit.py \
  tests/test_workouts663.py \
  tests/test_browser_qualification511.py::test_511_every_browser_module_in_disposable_qualification
echo "RELEASE_720_SCOPED_BACKEND=PASSED"

bash scripts/tracker-browser-qualify.sh "$ROOT" "$PY" \
  --targeted-strict workout-manage719
echo "RELEASE_720_SCOPED_BROWSER=PASSED"
echo "RELEASE_720_SCOPED_QUALIFICATION=PASSED_NOT_FULL_SUITE"
