#!/usr/bin/env bash
# Release 698: narrow visual-regression infrastructure qualification.
# Actual pinned-baseline browser comparisons run ONLY in tracker-preview698.sh.
set -Eeuo pipefail
[[ $# == 1 && -x "$1" ]] || {
  echo "Configured Python required" >&2
  exit 2
}
PY="$1"
ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd -P)"
[[ "$PWD" == "$ROOT" && "$ROOT" != /opt/tracker ]] || {
  echo "Release 698 source gate requires detached candidate worktree" >&2
  exit 2
}

bash -n scripts/tracker-preview698.sh
bash -n scripts/tracker-release-scoped698.sh
"$PY" -m py_compile \
  scripts/tracker_visual_regression698.py \
  tests/test_visual_regression698.py
"$PY" - <<'PY'
from pathlib import Path
runner = Path("scripts/tracker-preview698.sh").read_text(encoding="utf-8")
assert "git worktree add --detach" in runner
assert "TRACKER_DATA_DIR=\"$BASE_DATA\"" in runner
assert "TRACKER_DATA_DIR=\"$CANDIDATE_DATA\"" in runner
assert "git diff --check" in runner
assert "RELEASE_698_PREVIEW=PASSED_ISOLATED_NO_INSTALL" in runner
assert "scripts/tracker_visual_regression698.py" in runner
assert "tracker-prod" not in runner
print("RELEASE_698_SOURCE_GUARD=PASSED")
PY
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_visual_regression698.py \
  tests/test_ui_foundation679.py
echo "RELEASE_698_SOURCE_TESTS=PASSED"
echo "RELEASE_698_SCOPED=PASSED"
