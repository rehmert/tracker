#!/usr/bin/env bash
# Release 694: focused navigation qualification for guarded DEV deploy.
# No full suite, writes, network downloads, or installed-data access.
set -Eeuo pipefail

[[ $# == 1 && -x "$1" ]] || {
  echo "Configured Python required" >&2
  exit 2
}
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "$ROOT" != /opt/tracker ]] || {
  echo "Run in detached release candidate worktree" >&2
  exit 2
}

"$PY" -m py_compile \
  tests/test_navigation_focus.py \
  tests/test_nav_preferences_v23.py \
  tests/test_inventory_alerts_nav.py \
  tests/browser/test_navigation.py
"$PY" - <<'PY'
from pathlib import Path
from jinja2 import Environment
Environment().parse(Path('app/templates/base.html').read_text(encoding='utf-8'))
print('RELEASE_694_JINJA_SYNTAX=PASSED')
PY

command -v node >/dev/null 2>&1 || {
  echo "Release 694 needs installed Node.js for syntax validation" >&2
  exit 2
}
node --check app/static/nav_sort.js
node --check app/static/tracker_focus.js
echo "RELEASE_694_JS_SYNTAX=PASSED"

"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_navigation_focus.py \
  tests/test_nav_preferences_v23.py \
  tests/test_inventory_alerts_nav.py
echo "RELEASE_694_SOURCE_TESTS=PASSED"
echo "RELEASE_694_SCOPED=PASSED"
