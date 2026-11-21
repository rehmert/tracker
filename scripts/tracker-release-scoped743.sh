#!/usr/bin/env bash
# Release 743: cross-cutting security/dependency/readiness + CSS/global UX regression.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "${TRACKER_DATA_DIR:-}" == /tmp/* ]] ||
  { echo "Release 743 requires isolated source/data" >&2; exit 2; }
for script in scripts/tracker-qualify743.sh scripts/tracker-install743.sh \
  scripts/tracker-release-scoped743.sh scripts/tracker-release.sh; do
  bash -n "$script"
done
"$PY" -m py_compile app/routers/pages.py app/routers/supplies.py \
  tests/test_release742_consolidated_ux_performance.py \
  scripts/tracker_security_readiness743.py \
  scripts/tracker_browser_provenance743.py \
  scripts/tracker_stage_chain743.py \
  tests/test_release743_security_deps_chain_css.py
echo "RELEASE_743_COMPILE=PASSED"
"$PY" -c 'from pathlib import Path; from jinja2 import Environment; e=Environment(); [e.parse(Path(p).read_text(encoding="utf-8")) for p in ("app/templates/base.html","app/templates/supplies.html","app/templates/calendar.html")]'
echo "RELEASE_743_BASE_TEMPLATE=PASSED"
"$PY" -B scripts/tracker_security_readiness743.py
echo "RELEASE_743_CURRENT_CSRF_INVENTORY=PASSED_REPORT_ONLY"
if "$PY" -B scripts/tracker_security_readiness743.py --require-strict-ready >/dev/null; then
  echo "RELEASE_743_BLOCKED=Global CSRF readiness gate unexpectedly authorized" >&2; exit 12
else
  rc=$?
  [[ "$rc" == 3 ]] || { echo "RELEASE_743_BLOCKED=Unexpected CSRF error" >&2; exit 13; }
fi
echo "RELEASE_743_GLOBAL_CSRF_ENFORCEMENT=UNCHANGED_BLOCKED"
"$PY" - <<'PY'
from pathlib import Path
import os
from playwright.sync_api import sync_playwright
from scripts.tracker_browser_provenance743 import snapshot, validate
with sync_playwright() as p:
    supplied = os.environ.get("TRACKER_TEST_CHROMIUM_PATH")
    executable = Path(supplied if supplied else p.chromium.executable_path)
    result = validate(snapshot(executable))
assert result["python"].startswith("3.13.")
assert result["playwright"] == "1.64.1"
print("RELEASE_743_CHROMIUM_OS_FINGERPRINT=READ_ONLY_CAPTURED")
PY
# Isolate browser CSS contract failures as sanitized stage exit categories;
# raw pytest output and JUnit remain ONLY in disposable private /tmp QA data.
"$PY" - <<'PY'
from pathlib import Path
import os
import subprocess
import sys
from xml.etree import ElementTree

root = Path(os.environ["TRACKER_DATA_DIR"])
xml = root / "css743-diagnostic.xml"
log = root / "css743-diagnostic.log"
names = (
    "CSS743_COUNT", "CSS743_PRIMARY_DISPLAY", "CSS743_PRIMARY_HEIGHT",
    "CSS743_GYM_NAV_DISPLAY", "CSS743_TARGET_COUNT", "CSS743_TARGET_HEIGHT",
    "CSS743_KEYBOARD_FOCUS", "CSS743_MENU_OPEN", "CSS743_OVERFLOW",
)
cmd = [
    sys.executable, "-m", "pytest", "-q", "--tb=short", "--maxfail=1",
    "--junitxml=" + str(xml),
    "tests/test_release743_security_deps_chain_css.py::test_743_consolidated_css_computed_accessibility_contract",
]
with log.open("x", encoding="utf-8") as output:
    result = subprocess.run(cmd, stdout=output, stderr=subprocess.STDOUT,
                            check=False)
if result.returncode:
    found = ""
    try:
        failure = ElementTree.parse(xml).getroot().find(".//failure")
        if failure is not None:
            message = str(failure.attrib.get("message", "")) + str(failure.text or "")
            found = next((name for name in names if name in message), "")
    except (OSError, ElementTree.ParseError):
        pass
    if not found:
        print("RELEASE_743_CSS_DIAGNOSTIC=UNCLASSIFIED", flush=True)
        sys.exit(69)
    print("RELEASE_743_CSS_DIAGNOSTIC=" + found, flush=True)
    sys.exit(51 + names.index(found))
print("RELEASE_743_CSS_CHROMIUM=PASSED_ALL_WIDTHS_AND_THEMES", flush=True)
PY
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_release743_security_deps_chain_css.py \
  tests/test_release742_consolidated_ux_performance.py || exit 42
echo "RELEASE_743_INTEGRATED_NEW_TESTS=PASSED"
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
echo "RELEASE_743_SECURITY_DEPENDENCY_CONTROLLER_CSS=PASSED"
echo "RELEASE_743_SCOPED_QUALIFICATION=PASSED_NOT_FULL_SUITE"
