#!/usr/bin/env bash
# Release 703: only Vitals/Compound editor presentation and historical guards.
# Run in detached disposable candidate, not installed DEV or PROD.
set -Eeuo pipefail
[[ "$#" == 1 && -x "$1" ]] || {
  echo "Usage: tracker-release-scoped703.sh CONFIGURED_PYTHON" >&2
  exit 2
}
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "$ROOT" != /opt/tracker ]] || {
  echo "Release 703 gate requires detached candidate worktree" >&2
  exit 2
}
bash -n scripts/tracker-preview703.sh
bash -n scripts/tracker-release-scoped703.sh
"$PY" -m py_compile \
  tests/test_mobile_edit_actions703.py \
  tests/browser/test_mobile_edit_actions703.py

"$PY" - <<'PY'
from pathlib import Path
from jinja2 import Environment
css = Path("app/static/css/tracker-mobile-edit-actions703.css").read_text(encoding="utf-8")
for path in ("app/templates/vitals_edit.html", "app/templates/compound_edit.html"):
    template = Path(path).read_text(encoding="utf-8")
    Environment().parse(template)
    assert template.count("tracker-mobile-edit-actions703.css?v=703") == 1
    assert template.count('class="tracker-mobile-edit-actions703"') + template.count(
        'class="ux673-action-row tracker-mobile-edit-actions703"'
    ) == 1
assert css.count("{") == css.count("}")
assert css.count("/*") == css.count("*/")
assert "position: sticky;" in css
assert ":root.tracker-mobile-editing" in css
print("RELEASE_703_JINJA_CSS_SYNTAX=PASSED")
PY

# The Compound model/identity tests mutate ONLY the disposable SQLite
# database selected by TRACKER_DATA_DIR, never the installed database.
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_mobile_edit_actions703.py \
  tests/test_vitals_edit_guard.py \
  tests/test_vitals_edit_parity.py \
  tests/test_release_372_mobile_vitals.py::test_vitals_edit_keeps_numeric_inputs \
  tests/test_release_371_time_entry.py::test_logging_forms_retain_native_fallback \
  tests/test_stage31_compounds.py::test_compound_edit_and_search_preserves_identity \
  tests/test_stage31_compounds.py::test_compound_edit_rejects_duplicate_and_unit_change_with_vial \
  tests/test_ui_action_cleanup672.py::test_672_cancel_controls_consistent_on_editor_pages

echo "RELEASE_703_SOURCE_TESTS=PASSED"
echo "RELEASE_703_SCOPED=PASSED"
