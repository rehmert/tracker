#!/usr/bin/env bash
# Release 669: focused, isolated saved-food editor qualification only.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Expected configured Python executable" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && -d tests ]] || { echo "Requires isolated candidate worktree" >&2; exit 2; }
bash -n scripts/tracker-release-scoped669.sh
bash -n scripts/tracker-release669.sh
bash -n scripts/tracker-preview669.sh
bash -n scripts/tracker-release.sh
"$PY" -m py_compile app/routers/food.py tests/test_food_saved_edit669.py scripts/tracker-food-review669.py
"$PY" - <<'PY'
from pathlib import Path
from jinja2 import Environment
for path in ("app/templates/food.html", "app/templates/food_saved_edit669.html"):
    Environment().parse(Path(path).read_text(encoding="utf-8"))
print("RELEASE_669_FOOD_TEMPLATE_SYNTAX=PASSED")
PY
"$PY" scripts/tracker-food-review669.py \
  --root "$ROOT" --base c5ca4e1e226408b6d5784794dab5f73205b95c36 \
  --target "$(git rev-parse HEAD)"
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_food_saved_edit669.py \
  tests/test_food_quick375.py \
  tests/test_food_search380.py \
  tests/test_food_bundle376.py \
  tests/test_food_quick384.py \
  tests/test_release641_food_zero.py
echo "RELEASE_669_FOCUSED_SAVED_FOOD_REGRESSIONS=PASSED"
