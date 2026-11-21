#!/usr/bin/env bash
# Release 732: medication delete, dependent rows, browser confirmation.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "${TRACKER_DATA_DIR:-}" == /tmp/* ]] ||
  { echo "Release 732 requires isolated source/data" >&2; exit 2; }
for script in scripts/tracker-qualify732.sh scripts/tracker-install732.sh \
    scripts/tracker-release-scoped732.sh scripts/tracker-release.sh; do
  bash -n "$script"
done
"$PY" -m py_compile app/routers/regimen635.py \
  tests/test_release732_medication_delete.py
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release732_medication_delete.py \
  tests/test_release635_regimen.py \
  tests/test_release731_tablet_tracking.py \
  tests/test_release639_supplement_facts.py \
  tests/test_release636_regimen_catalog.py \
  tests/browser/test_regimen_catalog638_ui.py \
  tests/browser/test_regimen_facts639_ui.py
echo "RELEASE_732_REGIMEN_DELETE_TESTS=PASSED"
echo "RELEASE_732_SCOPED_QUALIFICATION=PASSED_NOT_FULL_SUITE"
