#!/usr/bin/env bash
# Release 699: focused density CSS consolidation qualification.
# Side effects: tests only in detached candidate worktree. No full suite.
set -Eeuo pipefail
[[ "$#" == 1 && -x "$1" ]] || {
  echo "Usage: tracker-release-scoped699.sh PATH_TO_CONFIGURED_PYTHON" >&2
  exit 2
}
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "$ROOT" != /opt/tracker ]] || {
  echo "Release 699 tests require an isolated candidate worktree" >&2
  exit 2
}
bash -n scripts/tracker-preview699.sh
bash -n scripts/tracker-release-scoped699.sh
"$PY" -m py_compile \
  tests/test_css_consolidation699.py \
  tests/browser/test_css_parity699.py
"$PY" - <<'PY'
from pathlib import Path
from jinja2 import Environment
from collections import Counter
for name in (
  "app/static/css/tracker-layout-density685.css",
  "app/static/css/tracker-compact-aggressive686.css",
):
    css = Path(name).read_text(encoding="utf-8")
    assert css.count("{") == css.count("}"), name
    assert "display: none" not in css
    assert "font-size:" not in css
    assert "min-height: 44px" in css
Environment().parse(Path("app/templates/base.html").read_text(encoding="utf-8"))
print("RELEASE_699_CSS_JINJA_SYNTAX=PASSED")
PY
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_css_consolidation699.py \
  tests/test_layout_density685.py \
  tests/test_compact_spacing686.py \
  tests/test_dashboard_polish688.py::test_688_source_and_template_contract \
  tests/test_overview_density690.py::test_690_dashboard_asset_and_content_contract \
  tests/test_ui_foundation679.py::test_679_component_layer_is_loaded_and_namespaced
echo "RELEASE_699_SOURCE_TESTS=PASSED"
echo "RELEASE_699_SCOPED=PASSED"
