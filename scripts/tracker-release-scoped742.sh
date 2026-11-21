#!/usr/bin/env bash
# Release 742: cross-cutting security/dependency/readiness + CSS/global UX regression.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "${TRACKER_DATA_DIR:-}" == /tmp/* ]] ||
  { echo "Release 742 requires isolated source/data" >&2; exit 2; }
for script in scripts/tracker-qualify742.sh scripts/tracker-install742.sh \
  scripts/tracker-release-scoped742.sh scripts/tracker-release.sh; do
  bash -n "$script"
done
"$PY" -m py_compile app/routers/pages.py app/routers/supplies.py \
  tests/test_release742_consolidated_ux_performance.py \
  scripts/tracker_security_readiness742.py \
  scripts/tracker_browser_provenance742.py \
  scripts/tracker_stage_chain742.py \
  tests/test_release742_security_deps_chain_css.py
echo "RELEASE_742_COMPILE=PASSED"
"$PY" -c 'from pathlib import Path; from jinja2 import Environment; e=Environment(); [e.parse(Path(p).read_text(encoding="utf-8")) for p in ("app/templates/base.html","app/templates/supplies.html","app/templates/calendar.html")]'
echo "RELEASE_742_BASE_TEMPLATE=PASSED"
"$PY" -B scripts/tracker_security_readiness742.py
echo "RELEASE_742_CURRENT_CSRF_INVENTORY=PASSED_REPORT_ONLY"
if "$PY" -B scripts/tracker_security_readiness742.py --require-strict-ready >/dev/null; then
  echo "RELEASE_742_BLOCKED=Global CSRF readiness gate unexpectedly authorized" >&2; exit 12
else
  rc=$?
  [[ "$rc" == 3 ]] || { echo "RELEASE_742_BLOCKED=Unexpected CSRF error" >&2; exit 13; }
fi
echo "RELEASE_742_GLOBAL_CSRF_ENFORCEMENT=UNCHANGED_BLOCKED"
"$PY" - <<'PY'
from pathlib import Path
import os
from playwright.sync_api import sync_playwright
from scripts.tracker_browser_provenance742 import snapshot, validate
with sync_playwright() as p:
    supplied = os.environ.get("TRACKER_TEST_CHROMIUM_PATH")
    executable = Path(supplied if supplied else p.chromium.executable_path)
    result = validate(snapshot(executable))
assert result["python"].startswith("3.13.")
assert result["playwright"] == "1.64.1"
print("RELEASE_742_CHROMIUM_OS_FINGERPRINT=READ_ONLY_CAPTURED")
PY
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release742_security_deps_chain_css.py \
  tests/test_release742_consolidated_ux_performance.py || exit 42
echo "RELEASE_742_INTEGRATED_NEW_TESTS=PASSED"
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_ui_foundation679.py \
  tests/test_shortcut_buttons676.py \
  tests/test_shortcut_buttons_browser676.py \
  tests/test_explanation_touch680.py \
  tests/test_workout_nav_density681.py \
  tests/test_release723_css_consolidation.py \
  tests/test_release569_dependency_baseline.py \
  tests/test_release626_dependency_evidence.py \
  tests/test_release705_dependency_readiness.py \
  tests/test_release705_dependency_replay.py \
  tests/test_release705_combined.py \
  tests/test_release705_dependency_acquire.py \
  tests/test_release590_csrf_gap_plan.py \
  tests/test_release627_csrf_reconciliation.py \
  tests/test_release621_csrf_form_crosswalk.py \
  tests/test_csrf_all_registered_negative705.py \
  tests/test_release741_integrated_macd_mobile.py \
  tests/test_supply_stock_filters.py \
  tests/test_supply_stock_health.py \
  tests/test_supply_use_preview.py \
  tests/test_calendar_workbench.py \
  tests/test_calendar_review_agenda.py \
  tests/test_record_explorer_template_regression.py || exit 43
echo "RELEASE_742_SECURITY_DEPENDENCY_CONTROLLER_CSS=PASSED"
echo "RELEASE_742_SCOPED_QUALIFICATION=PASSED_NOT_FULL_SUITE"
