#!/usr/bin/env bash
# Release 694: scoped navigation and daily workflow qualification; no live writes.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" ]] || { echo "Run only in isolated candidate root" >&2; exit 2; }
bash -n scripts/tracker-release.sh
bash -n scripts/tracker-preview694.sh
bash -n scripts/tracker-release-scoped694.sh
"$PY" -m py_compile \
  scripts/tracker-review694.py \
  tests/test_everyday_navigation694.py \
  tests/test_dashboard_polish688.py \
  tests/test_release559_everyday_bundle.py
"$PY" - <<'PY'
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
source = Path("app/templates")
env = Environment(loader=FileSystemLoader(source))
for template in ("base.html", "dashboard.html", "mobile_today509.html",
                 "_daily_actions694.html", "quick_entry.html"):
    env.parse((source / template).read_text(encoding="utf-8"))
assert env.get_template("_daily_actions694.html").module.daily_actions694
print("RELEASE_694_JINJA_AND_MACRO_SYNTAX=PASSED")
PY
echo "RELEASE_694_TEST_SCOPE=NAVIGATION_DAILY_UI_FOCUSED_NO_FULL_SUITE"
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_everyday_navigation694.py \
  tests/test_navigation_focus.py \
  tests/test_release559_everyday_bundle.py \
  tests/test_dashboard_polish688.py \
  tests/test_release601_mobile_workflows.py \
  tests/test_shortcuts_toolbar687.py \
  tests/test_mobile_daily509.py
echo "RELEASE_694_NAVIGATION_DAILY_SCOPED_TESTS=PASSED"
