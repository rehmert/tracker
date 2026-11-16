#!/usr/bin/env bash
# Release 662: exact-source DEV-only rapid gym floor refinement qualification.
set -Eeuo pipefail
[[ "$#" == 1 && -x "$1" ]] || {
  echo "Usage: $0 PATH_TO_CONFIGURED_PYTHON" >&2; exit 2;
}
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && -d tests ]] || {
  echo "Run only from isolated candidate worktree" >&2; exit 2;
}

bash -n "$0"
bash -n scripts/tracker-workout-dev662.sh
bash -n scripts/tracker-release.sh
"$PY" -m py_compile \
  scripts/tracker-workout-review662.py \
  tests/test_workouts662.py \
  tests/browser/test_workouts_quick662.py
command -v node >/dev/null || {
  echo "Node.js required for JS gym-floor syntax qualification" >&2; exit 2;
}
node --check app/static/js/tracker-workouts662.js
node --check app/static/js/tracker-workouts659.js
"$PY" - <<'PY'
from pathlib import Path
from jinja2 import Environment
for path in (
    "app/templates/workout_quick659.html",
    "app/templates/workouts654.html",
    "app/templates/workout_analytics660.html",
    "app/templates/dashboard.html",
    "app/templates/_workout_dashboard661.html",
):
    Environment().parse(Path(path).read_text(encoding="utf-8"))
print("WORKOUT_662_JINJA_AND_JS_SYNTAX=PASSED")
PY
BASE=7456380bfe191cdc011a7dc692bd8c8cce59d1ed
TARGET="$(git rev-parse HEAD)"
"$PY" scripts/tracker-workout-review662.py \
  --root "$ROOT" --base "$BASE" --target "$TARGET"

"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_workouts662.py \
  tests/test_workouts659.py \
  tests/test_workouts660.py \
  tests/test_workout_dashboard661.py \
  tests/test_workouts658.py \
  tests/test_workouts657.py \
  tests/test_workouts656.py \
  tests/test_workouts655.py \
  tests/test_workouts654.py \
  tests/test_workout_dev_backup655.py \
  tests/test_tracker_instance_check653.py \
  tests/test_release_workflow.py \
  tests/test_prod_parallel_release508.py \
  tests/test_release629_qa_cadence.py
echo "WORKOUT_662_CHANGE_SCOPED_TESTS=PASSED"

"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/browser/test_workouts_quick662.py \
  tests/browser/test_workouts_quick659.py
echo "WORKOUT_662_PHONE_CHROMIUM=PASSED"
