#!/usr/bin/env bash
# Release 702: source/Jinja and previously protected Saved Food write regressions.
# Run only in isolated disposable candidate checkout, never installed data.
set -Eeuo pipefail
[[ "$#" == 1 && -x "$1" ]] || {
  echo "Usage: tracker-release-scoped702.sh CONFIGURED_PYTHON" >&2
  exit 2
}
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "$ROOT" != /opt/tracker ]] || {
  echo "Release 702 gate requires detached candidate worktree" >&2
  exit 2
}

bash -n scripts/tracker-preview702.sh
bash -n scripts/tracker-release-scoped702.sh

"$PY" -m py_compile \
  tests/test_saved_food_mobile_actions702.py \
  tests/browser/test_saved_food_mobile_actions702.py

"$PY" - <<'PY'
from pathlib import Path
from jinja2 import Environment
template = Path("app/templates/food_saved_edit669.html").read_text(encoding="utf-8")
css = Path("app/static/css/tracker-saved-food-actions702.css").read_text(encoding="utf-8")
Environment().parse(template)
assert css.count("{") == css.count("}")
assert css.count("/*") == css.count("*/")
assert template.count('type="submit" class="primary"') == 1
assert template.count('name="version"') == 1
assert 'position: sticky;' in css
assert ':root.tracker-mobile-editing' in css
print("RELEASE_702_JINJA_CSS_SYNTAX=PASSED")
PY

# Exact existing Saved Food edit POST protections use in-memory SQLite
# or disposable TEST data, not installed DEV/PROD data. No full suite.
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_saved_food_mobile_actions702.py \
  tests/test_food_saved_edit669.py \
  tests/test_food_edit_buttons671.py \
  tests/test_ui_action_cleanup672.py
echo "RELEASE_702_SOURCE_TESTS=PASSED"
echo "RELEASE_702_SCOPED=PASSED"
