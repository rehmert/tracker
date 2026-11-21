#!/usr/bin/env bash
# Release 737: visual Add disclosure arrows, no backend or schema changes.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "${TRACKER_DATA_DIR:-}" == /tmp/* ]] ||
  { echo "Release 737 requires isolated source/data" >&2; exit 2; }
for script in scripts/tracker-qualify737.sh scripts/tracker-install737.sh \
    scripts/tracker-release-scoped737.sh scripts/tracker-release.sh; do
  bash -n "$script"
done
"$PY" -m py_compile tests/test_release736_regimen_add_chevron.py tests/test_release737_native_regimen_disclosures.py
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release736_regimen_add_chevron.py \
  tests/test_release737_native_regimen_disclosures.py \
  tests/test_release734_regimen_button_parity.py \
  tests/test_release733_regimen_macd_actions.py \
  tests/test_release732_medication_delete.py
echo "RELEASE_737_DISCLOSURE_CHEVRON_TESTS=PASSED"
echo "RELEASE_737_SCOPED_QUALIFICATION=PASSED_NOT_FULL_SUITE"
