#!/usr/bin/env bash
# Release 670: focused recorded-food action button regression.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Expected configured Python executable" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && -d tests ]] || { echo "Requires isolated candidate worktree" >&2; exit 2; }
bash -n scripts/tracker-release-scoped670.sh
bash -n scripts/tracker-preview670.sh
bash -n scripts/tracker-release670.sh
"$PY" -m py_compile tests/test_food_saved_edit669.py
"$PY" - <<'PY'
from pathlib import Path
from jinja2 import Environment
Environment().parse(Path("app/templates/food.html").read_text(encoding="utf-8"))
print("RELEASE_670_FOOD_TEMPLATE_SYNTAX=PASSED")
PY
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_food_action670.py \
  tests/test_food_saved_edit669.py \
  tests/test_food_quick375.py
echo "RELEASE_670_FOCUSED_FOOD_ACTION_REGRESSIONS=PASSED"
