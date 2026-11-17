#!/usr/bin/env bash
# Release 674: isolated productivity and correction recovery qualification.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || { echo "Configured Python executable required" >&2; exit 2; }
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && -d tests ]] || { echo "Expected isolated candidate worktree" >&2; exit 2; }
bash -n scripts/tracker-release-scoped674.sh
bash -n scripts/tracker-preview674.sh
bash -n scripts/tracker-release674.sh
"$PY" -m py_compile \
  app/routers/data_quality674.py \
  app/routers/recovery674.py \
  app/routers/mobile509.py \
  app/routers/workouts659.py \
  app/daily_summary674.py \
  app/workout_progression674.py \
  tests/test_integrated_productivity674.py
"$PY" - <<'PY'
from pathlib import Path
from jinja2 import Environment
pages = (
    "base.html", "mobile_today509.html", "data_quality674.html",
    "workout_quick659.html", "workout_corrections668.html",
)
for page in pages:
    print(f"RELEASE_674_JINJA_CHECK={page}", flush=True)
    Environment().parse((Path("app/templates") / page).read_text(encoding="utf-8"))
print("RELEASE_674_JINJA_SYNTAX=PASSED")
PY
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_integrated_productivity674.py \
  tests/test_mobile_daily509.py \
  tests/test_workout_corrections668.py \
  tests/test_workouts659.py \
  tests/test_workouts667.py \
  tests/test_workout_offline668.py \
  tests/test_workout_guides668.py \
  tests/test_food_saved_edit669.py \
  tests/test_mobile_app_shell507.py
echo "RELEASE_674_INTEGRATED_PRODUCTIVITY_QUALIFICATION=PASSED"
