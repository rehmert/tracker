#!/usr/bin/env bash
# Release 695: daily workflow presentation and navigation qualification.
# Change-scoped only. Does not access installed records or require downloads.
set -Eeuo pipefail

[[ $# == 1 && -x "$1" ]] || {
  echo "Configured Python required" >&2
  exit 2
}
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "$ROOT" != /opt/tracker ]] || {
  echo "Release 695 gate requires detached candidate worktree" >&2
  exit 2
}

"$PY" -m py_compile \
  tests/test_daily_flow695.py \
  tests/browser/test_daily_flow695.py
"$PY" - <<'PY'
from pathlib import Path
from jinja2 import Environment
env = Environment()
for name in ("mobile_today509.html", "quick_entry.html"):
    env.parse(Path("app/templates", name).read_text(encoding="utf-8"))
print("RELEASE_695_JINJA_SYNTAX=PASSED")
PY
"$PY" - <<'PY'
from pathlib import Path
css = Path("app/static/css/tracker-productivity674.css").read_text(encoding="utf-8")
assert css.count("{") == css.count("}")
assert ".tracker-daily509 .ux695-summary-link" in css
print("RELEASE_695_SCOPED_CSS=PASSED")
PY
if command -v node >/dev/null 2>&1; then
  node --check app/static/js/tracker-mobile-daily509.js
  node --check app/static/js/tracker-quick-entry.js
  echo "RELEASE_695_UNCHANGED_JS_SYNTAX=PASSED"
fi

"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_daily_flow695.py \
  tests/test_release601_mobile_workflows.py \
  tests/test_release559_everyday_bundle.py \
  tests/test_mobile_daily509.py \
  tests/test_integrated_productivity674.py::test_674_templates_routes_and_no_auto_log_contract \
  tests/test_integrated_productivity674.py::test_674_read_only_routes_render_without_new_schema
echo "RELEASE_695_SOURCE_TESTS=PASSED"
echo "RELEASE_695_SCOPED=PASSED"
