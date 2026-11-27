#!/usr/bin/env bash
# Release 794: consolidated planning and daily workflows, notes and browser regression only.
set -Eeuo pipefail
umask 077
PY="${1:-}"
[[ -n "$PY" && -x "$PY" ]] || { echo "RELEASE_794_BLOCKED=Python missing" >&2; exit 1; }
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT" PYTHONDONTWRITEBYTECODE=1
REPORT="$(mktemp /tmp/tracker794-test-report.XXXXXXXX)"
trap 'rm -f -- "$REPORT"' EXIT
rc=0
"$PY" -B -m pytest -q --tb=short --disable-warnings --junitxml="$REPORT" \
 "tests/test_workflow_consolidation794.py" \
 "tests/test_labs_overview.py" \
 "tests/test_release778_regimen_return.py" \
 "tests/test_release775_google_tasks_navigation.py" \
 "tests/test_release766_combined.py" \
 "tests/test_workouts659.py" \
 "tests/test_workouts662.py" \
 "tests/test_release782_compact_gym.py" \
 "tests/test_protocol_schedule_preview.py" \
 "tests/test_protocol_inventory_handoff.py" \
 "tests/test_integrated_daily790.py" \
 "tests/test_compact_daily_actions791.py" \
 "tests/test_calendar_action_buttons787.py" \
 "tests/test_consolidated_workspaces792.py" \
 "tests/test_release602_mobile_bundle.py::test_602_dose_draft_fastpath_and_original_form" \
 "tests/test_release602_mobile_bundle.py::test_602_mobile_guidance_has_no_write_or_prefill_actions" || rc=$?
# Emit only allowlisted synthetic test names and source line numbers; no raw
# exceptions, locals, record data, paths or XML leave the isolated host.
"$PY" -B - "$REPORT" <<'PYCODE'
import re
import sys
import xml.etree.ElementTree as ET
try:
    tree = ET.parse(sys.argv[1])
except (OSError, ET.ParseError):
    print("TARGETED_794_DIAGNOSTIC_REPORT=FAILED")
else:
    for case in tree.iter("testcase"):
        failure = case.find("failure")
        if failure is None:
            failure = case.find("error")
        if failure is None:
            continue
        name = case.get("name", "")
        if case.get("classname", "") != "tests.test_workflow_consolidation794":
            continue
        if not re.fullmatch(r"test_794_[a-z0-9_]+(?:\\[[0-9]+\\])?", name):
            continue
        key = re.sub(r"[^A-Z0-9_]", "_", name.upper())
        line = re.search(r"tests/test_workflow_consolidation794\\.py:(\\d+):", failure.text or "")
        if line:
            key += "_LINE_" + line.group(1)
        print("TARGETED_794_" + key + "=FAILED")
PYCODE
[[ "$rc" == 0 ]] || exit "$rc"
echo "RELEASE_794_SCOPED=PASSED"
