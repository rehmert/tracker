#!/usr/bin/env bash
# Release 731: additive tablet schema and native regimen UI, focused QA only.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "${TRACKER_DATA_DIR:-}" == /tmp/* ]] ||
  { echo "Release 731 requires isolated source/data" >&2; exit 2; }
for s in scripts/tracker-release.sh scripts/tracker-qualify731.sh \
    scripts/tracker-install731.sh scripts/tracker-release-scoped731.sh; do
  bash -n "$s"
done
"$PY" -m py_compile app/models.py app/regimen_tablets731.py \
  app/routers/regimen635.py tests/test_release731_tablet_tracking.py \
  tests/browser/test_release731_tablet_tracking.py
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release731_tablet_tracking.py \
  tests/browser/test_release731_tablet_tracking.py \
  tests/test_release635_regimen.py \
  tests/test_release635_schema_review.py \
  tests/test_release639_supplement_facts.py \
  tests/test_release639_schema_review.py \
  tests/test_release636_regimen_catalog.py \
  tests/browser/test_regimen_catalog638_ui.py \
  tests/browser/test_regimen_facts639_ui.py \
  tests/test_release730_medication_prefill.py
echo "RELEASE_731_TABLET_TESTS=PASSED"
echo "RELEASE_731_SCOPED_QUALIFICATION=PASSED_NOT_FULL_SUITE"
