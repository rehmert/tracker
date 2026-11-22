#!/usr/bin/env bash
# Release 746 isolated source-only security/dependency/MACD/global-CSS qualification.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "$TRACKER_DATA_DIR" == /tmp/* ]] ||
  { echo "Private isolated data required" >&2; exit 2; }
for script in scripts/tracker-qualify746.sh scripts/tracker-install746.sh \
  scripts/tracker-release-scoped746.sh scripts/tracker-release.sh; do
  bash -n "$script"
done
"$PY" -B -m py_compile scripts/tracker_host_evidence746.py \
  tests/test_release746_hardening.py tests/test_release746_strict_water.py
echo "RELEASE_746_COMPILE=PASSED"
"$PY" -B -m pytest -q --tb=short --maxfail=1 \
  tests/test_release746_hardening.py tests/test_release746_strict_water.py || exit 42
echo "RELEASE_746_SECURITY_DEPENDENCY_MACD_CSS=PASSED"
"$PY" -B -m pytest -q --tb=short --maxfail=1 \
  tests/test_layout_density685.py tests/test_compact_spacing686.py \
  tests/test_shortcuts_toolbar687.py tests/test_dashboard_polish688.py \
  tests/test_workout_footnote_spacing689.py tests/test_css_consolidation699.py \
  tests/test_css_consolidation700.py tests/test_overview_density690.py \
  tests/browser/test_css_parity699.py tests/browser/test_css_parity700.py || exit 43
echo "RELEASE_746_SHARED_CORE_BROWSER_CSS_PARITY=PASSED"
"$PY" -B -m pytest -q --tb=short --maxfail=1 \
  tests/test_release741_integrated_macd_mobile.py \
  tests/test_release745_macd_css.py tests/test_release738_integrated_macd_mobile.py \
  tests/test_release569_dependency_baseline.py \
  tests/test_release705_dependency_readiness.py \
  tests/test_release520_csrf_multipart.py || exit 44
echo "RELEASE_746_HISTORICAL_SECURITY_DEPENDENCY_MACD=PASSED"
"$PY" -B scripts/tracker_dependency_baseline569.py --instance DEV || exit 45
echo "RELEASE_746_ACTUAL_DEV_PYTHON_BASELINE=PASSED"
echo "RELEASE_746_SCOPED_QUALIFICATION=PASSED_NOT_FULL_SUITE"
