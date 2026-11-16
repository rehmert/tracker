#!/usr/bin/env bash
# Release 655: DEV-only, change-scoped workout routines qualification.
# Source and TEST_DATA_DIR must be isolated; never executes a deployment.
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
bash -n scripts/tracker-workout-dev655.sh
"$PY" -m py_compile \
  app/workout_models655.py app/routers/workouts655.py app/routers/workouts654.py \
  tests/test_workouts655.py tests/test_workouts654.py \
  scripts/tracker-workout-schema-review655.py scripts/tracker-workout-dev-backup655.py \
  tests/test_workout_dev_backup655.py
command -v node >/dev/null || {
  echo "Node.js required for scoped Workout JavaScript syntax check" >&2; exit 2;
}
node --check app/static/js/tracker-workouts655.js
"$PY" - <<'PY'
from pathlib import Path
from jinja2 import Environment
for p in (
    Path("app/templates/workouts654.html"),
    Path("app/templates/workout_routines655.html"),
    Path("app/templates/workout_routine_detail655.html"),
):
    Environment().parse(p.read_text(encoding="utf-8"))
print("WORKOUT_655_JINJA_AND_JAVASCRIPT_SYNTAX=PASSED")
PY
BASE=419e0c199d6a5dc373df7de1401953a056cac8d1
TARGET="$(git rev-parse HEAD)"
"$PY" scripts/tracker-workout-schema-review655.py \
  --root "$ROOT" --base "$BASE" --target "$TARGET"
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_workouts655.py \
  tests/test_workouts654.py \
  tests/test_coa_backup652.py \
  tests/test_dev_attachment_gate650.py::test_650_dev_missing_only_may_be_reported_without_mutation \
  tests/test_dev_attachment_gate650.py::test_650_dev_policy_fails_closed_on_bad_evidence \
  tests/test_dev_attachment_gate650.py::test_650_only_exact_dev_instance_is_eligible \
  tests/test_tracker_instance_check653.py \
  tests/test_release_workflow.py \
  tests/test_prod_parallel_release508.py \
  tests/test_release629_qa_cadence.py
echo "WORKOUT_655_CHANGE_SCOPED_TESTS=PASSED"
