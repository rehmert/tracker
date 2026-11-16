#!/usr/bin/env bash
# Release 654: isolated change-scoped Workout qualification (never deploys).
set -Eeuo pipefail
[[ "$#" == 1 && -x "$1" ]] || {
  echo "Usage: $0 PATH_TO_CONFIGURED_PYTHON" >&2; exit 2;
}
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && -d tests ]] || {
  echo "Run from isolated candidate worktree" >&2; exit 2;
}
bash -n "$0"
bash -n scripts/tracker-release.sh
"$PY" -m py_compile app/workout_models654.py app/routers/workouts654.py \
    scripts/tracker-workout-schema-review654.py tests/test_workouts654.py
"$PY" - <<'PY'
from pathlib import Path
from jinja2 import Environment
Environment().parse(Path("app/templates/workouts654.html").read_text(encoding="utf-8"))
print("WORKOUT_654_TEMPLATE_SYNTAX=PASSED")
PY
BASE=108bf3241bd747f6174dc7e65a8c01161af24e62
TARGET="$(git rev-parse HEAD)"
"$PY" scripts/tracker-workout-schema-review654.py \
    --root "$ROOT" --base "$BASE" --target "$TARGET"
"$PY" -m pytest -q --tb=short --maxfail=1 \
    tests/test_workouts654.py \
    tests/test_tracker_instance_check653.py \
    tests/test_release_workflow.py \
    tests/test_prod_parallel_release508.py \
    tests/test_release629_qa_cadence.py
echo "WORKOUT_654_CHANGE_SCOPED_TESTS=PASSED"
