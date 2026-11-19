#!/usr/bin/env bash
# Release 700: change-scoped qualification for two shared UI CSS files.
# Run in detached candidate only, never against installed DEV/PROD.
set -Eeuo pipefail

[[ "$#" == 1 && -x "$1" ]] || {
  echo "Usage: tracker-release-scoped700.sh CONFIGURED_PYTHON" >&2
  exit 2
}
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "$ROOT" != /opt/tracker ]] || {
  echo "Release 700 source gate must run in detached candidate worktree" >&2
  exit 2
}

bash -n scripts/tracker-preview700.sh
bash -n scripts/tracker-release-scoped700.sh
"$PY" -m py_compile \
  tests/test_css_consolidation700.py \
  tests/browser/test_css_parity700.py

"$PY" - <<'PY'
from pathlib import Path
from jinja2 import Environment
for path in (
    "app/static/css/tracker-shortcuts-toolbar687.css",
    "app/static/css/tracker-dashboard-polish688.css",
):
    css = Path(path).read_text(encoding="utf-8")
    assert css.count("{") == css.count("}"), path
    assert "font-size: 0" not in css
Environment().parse(Path("app/templates/base.html").read_text(encoding="utf-8"))
print("RELEASE_700_CSS_JINJA_SYNTAX=PASSED")
PY

"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_css_consolidation700.py \
  tests/test_shortcuts_toolbar687.py \
  tests/test_dashboard_polish688.py \
  tests/test_workout_footnote_spacing689.py \
  tests/test_overview_density690.py::test_690_dashboard_asset_and_content_contract
echo "RELEASE_700_SOURCE_TESTS=PASSED"
echo "RELEASE_700_SCOPED=PASSED"
