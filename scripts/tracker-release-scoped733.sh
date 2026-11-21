#!/usr/bin/env bash
# Release 733: visible Regimen Edit actions, module-scoped QA.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "${TRACKER_DATA_DIR:-}" == /tmp/* ]] ||
  { echo "Release 733 requires isolated source/data" >&2; exit 2; }
for script in scripts/tracker-qualify733.sh scripts/tracker-install733.sh \
    scripts/tracker-release-scoped733.sh scripts/tracker-release.sh; do
  bash -n "$script"
done
"$PY" -m py_compile tests/test_release733_regimen_macd_actions.py
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release733_regimen_macd_actions.py \
  tests/test_release732_medication_delete.py \
  tests/test_release731_tablet_tracking.py \
  tests/test_release635_regimen.py \
  tests/test_release636_regimen_catalog.py
echo "RELEASE_733_REGIMEN_EDIT_ACTION_TESTS=PASSED"
echo "RELEASE_733_SCOPED_QUALIFICATION=PASSED_NOT_FULL_SUITE"
