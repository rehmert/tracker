#!/usr/bin/env bash
# Release 704: one consolidated UX qualification with existing workflow guards.
# Only disposable candidate checkout; no installed DEV/PROD database.
set -Eeuo pipefail
[[ "$#" == 1 && -x "$1" ]] || {
  echo "Usage: tracker-release-scoped704.sh CONFIGURED_PYTHON" >&2
  exit 2
}
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "$ROOT" != /opt/tracker ]] || {
  echo "Release 704 gate requires detached candidate worktree" >&2
  exit 2
}
bash -n scripts/tracker-preview704.sh
bash -n scripts/tracker-release-scoped704.sh
node --check app/static/js/tracker-lab-sticky-actions704.js
echo "RELEASE_704_LAB_GUARD_JS_SYNTAX=PASSED"
"$PY" -m py_compile \
  tests/test_consolidated_forms704.py \
  tests/browser/test_consolidated_forms704.py
"$PY" - <<'PY'
from pathlib import Path
from jinja2 import Environment
css = Path("app/static/css/tracker-consolidated-forms704.css").read_text(encoding="utf-8")
assert css.count("{") == css.count("}")
assert css.count("/*") == css.count("*/")
assert ":root.tracker-mobile-editing" in css
for page in ("page_edit", "workout_backfill658", "lab_form"):
    source = Path(f"app/templates/{page}.html").read_text(encoding="utf-8")
    assert source.count("tracker-consolidated-forms704.css?v=704") == 1
    assert source.count("tracker-form-actions704--") == 1
    Environment().parse(source)
print("RELEASE_704_JINJA_CSS_SYNTAX=PASSED")
PY

# Focused historical write-path and JS-guard contracts; isolated SQLite.
# No full application suite. Release 702/703 original tests are retained.
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_consolidated_forms704.py \
  tests/test_saved_food_mobile_actions702.py \
  tests/test_mobile_edit_actions703.py \
  tests/test_workouts658.py \
  tests/test_lab_entry_safeguards.py \
  tests/test_lab_entry_review_ux.py \
  tests/test_lab_review_navigation.py \
  tests/test_lab_layout_reuse.py \
  tests/test_vitals_edit_guard.py \
  tests/test_vitals_edit_parity.py \
  tests/test_ui_action_cleanup672.py
echo "RELEASE_704_SOURCE_TESTS=PASSED"
echo "RELEASE_704_SCOPED=PASSED"
