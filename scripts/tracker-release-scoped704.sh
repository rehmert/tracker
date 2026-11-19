#!/usr/bin/env bash
# Release 704: consolidated UI milestone; isolate all historical writes.
# No unreviewed dependency updates or strict-CSRF enforcement changes.
set -Eeuo pipefail
[[ "$#" == 1 && -x "$1" ]] || {
  echo "Usage: tracker-release-scoped704.sh CONFIGURED_PYTHON" >&2
  exit 2
}
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "$ROOT" != /opt/tracker ]] || {
  echo "Release 704 requires a detached candidate worktree" >&2
  exit 2
}
[[ -n "${TRACKER_DATA_DIR:-}" && "$TRACKER_DATA_DIR" != /opt/tracker/data ]] || {
  echo "Release 704 refuses installed data" >&2
  exit 2
}
bash -n scripts/tracker-preview704.sh
bash -n scripts/tracker-release-scoped704.sh
"$PY" -m py_compile \
  scripts/tracker-ux-audit704.py \
  scripts/tracker-latency704.py \
  tests/test_consolidated_ux704.py \
  tests/browser/test_consolidated_ux704.py

# No changes to existing security policy or dependency requirements.
"$PY" - <<'PY'
from pathlib import Path
from jinja2 import Environment
forms = (
 "dose_edit.html","page_edit.html","workout_backfill658.html",
 "preparation_edit.html","lab_form.html",
)
jinja = Environment(extensions=["jinja2.ext.do"])
for form in forms:
    source=Path("app/templates",form).read_text(encoding="utf-8")
    jinja.parse(source)
    assert source.count("tracker-edit-actions704\"")==1,form
    assert source.count("tracker-edit-feedback704.js?v=704")==1,form
    assert source.count("tracker-edit-actions704.css?v=704")==1,form
css=Path("app/static/css/tracker-edit-actions704.css").read_text(encoding="utf-8")
assert css.count("{")==css.count("}")
assert css.count("/*")==css.count("*/")
assert "position: sticky;" in css and ":root.tracker-mobile-editing" in css
print("RELEASE_704_JINJA_CSS=PASSED")
PY

"$PY" scripts/tracker-ux-audit704.py
"$PY" scripts/tracker-quality-gate.py --source-only

# Focused existing API and source safeguards; all state-changing tests must
# use the completely private TRACKER_DATA_DIR from the preview.
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_consolidated_ux704.py \
  tests/test_dose_correction_page.py \
  tests/test_dose_correction_live_review.py \
  tests/test_dose_correction_inventory_preview.py \
  tests/test_release_373_mobile_dose.py \
  tests/test_workouts658.py \
  tests/test_lab_entry_review_ux.py \
  tests/test_lab_entry_safeguards.py \
  tests/test_lab_review_navigation.py \
  tests/test_lab_source_picker.py \
  tests/test_lab_layout_reuse.py \
  tests/test_ui_action_cleanup672.py \
  tests/test_saved_food_mobile_actions702.py \
  tests/test_mobile_edit_actions703.py \
  tests/test_release569_dependency_baseline.py

echo "RELEASE_704_SOURCE_TESTS=PASSED"
echo "RELEASE_704_SCOPED=PASSED"
