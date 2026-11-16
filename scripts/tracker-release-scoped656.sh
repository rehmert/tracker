#!/usr/bin/env bash
# Release 656: isolated Workout QR camera and progress qualification.
# Never runs against the live database; never deploys.
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
bash -n scripts/tracker-workout-dev656.sh
bash -n scripts/tracker-release.sh
"$PY" -m py_compile \
  app/routers/workouts656.py \
  scripts/tracker-workout-review656.py \
  tests/test_workouts656.py
command -v node >/dev/null 2>&1 || {
  echo "Node.js required for Release 656 QR scanner qualification" >&2; exit 2;
}
node --check app/static/js/tracker-workouts656.js
node --check scripts/tracker-workout-camera-test656.cjs
node scripts/tracker-workout-camera-test656.cjs
"$PY" - <<'PY'
from jinja2 import Environment
from pathlib import Path
for name in ("workout_progress656.html", "workouts654.html"):
    Environment().parse((Path("app/templates") / name).read_text(encoding="utf-8"))
print("WORKOUT_656_JINJA_SYNTAX=PASSED")
PY

BASE=b1d8ad1d3003d1f8ef2e5b3614ba1148076c5c25
TARGET="$(git rev-parse HEAD)"
"$PY" scripts/tracker-workout-review656.py \
  --root "$ROOT" --base "$BASE" --target "$TARGET"

"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_workouts656.py \
  tests/test_workouts655.py \
  tests/test_workouts654.py \
  tests/test_workout_dev_backup655.py \
  tests/test_tracker_instance_check653.py \
  tests/test_release_workflow.py \
  tests/test_prod_parallel_release508.py \
  tests/test_release629_qa_cadence.py

echo "WORKOUT_656_CHANGE_SCOPED_TESTS=PASSED"
