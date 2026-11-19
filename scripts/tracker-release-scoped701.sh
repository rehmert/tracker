#!/usr/bin/env bash
# Release 701: isolated Quick Add navigation and unchanged write-path checks.
# Change-scoped only; never execute against installed /opt/tracker.
set -Eeuo pipefail
[[ "$#" == 1 && -x "$1" ]] || {
  echo "Usage: tracker-release-scoped701.sh CONFIGURED_PYTHON" >&2
  exit 2
}
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "$ROOT" != /opt/tracker ]] || {
  echo "Release 701 gate requires detached candidate worktree" >&2
  exit 2
}

bash -n scripts/tracker-preview701.sh
bash -n scripts/tracker-release-scoped701.sh
"$PY" -m py_compile \
  tests/test_mobile_quick_actions701.py \
  tests/browser/test_mobile_quick_actions701.py

"$PY" - <<'PY'
from pathlib import Path
from jinja2 import Environment
sheet = Path("app/templates/_mobile_quick528.html").read_text(encoding="utf-8")
Environment().parse(sheet)
assert sheet.count('data-quick528-form=') == 3
assert sheet.count('data-quick528-choice=') == 3
assert '<a href="/workouts/quick">Log Workout Set</a>' in sheet
assert '<a href="/regimen#reg635-today">Log Supplements / Meds</a>' in sheet
print("RELEASE_701_JINJA_AND_WRITE_PATH_CONTRACT=PASSED")
PY

# Existing 528 tests exercise the SAME protected write routes, but ONLY
# against the isolated, empty TRACKER_DATA_DIR exported by the preview.
# No application-wide test suite and no CSRF changes.
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_mobile_quick_actions701.py \
  tests/test_mobile_quick528.py \
  tests/test_daily_flow695.py::test_695_today_has_one_early_recording_bar_and_no_duplicate_row \
  tests/test_daily_flow695.py::test_695_quick_entry_exposes_same_missing_recording_destinations
echo "RELEASE_701_SOURCE_TESTS=PASSED"
echo "RELEASE_701_SCOPED=PASSED"
