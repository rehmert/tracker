#!/usr/bin/env bash
# DEV-only, non-deploying, change-scoped COA QA. No full test suite.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
REF=feature/coa-multiple-attachments
EXPECTED_BASE=92f6193f509abcb12fd4c9a2f4c8d11854822044
fail() { echo "COA_QUALIFICATION=FAILED: $*" >&2; exit 1; }
[[ "$(id -u)" == 0 && -x "$PY" && -f /etc/tracker.env ]] || fail "Requires root on a configured Tracker host"
"$PY" - <<'PY'
import re
from pathlib import Path
labels=[]
for line in Path('/etc/tracker.env').read_text().splitlines():
    m=re.match(r'^\s*(?:export\s+)?TRACKER_INSTANCE\s*=(.*)$', line)
    if m: labels.append(m.group(1).strip().strip(chr(34)).strip(chr(39)).upper())
assert labels == ['DEV'], 'Refusing to run on a non-DEV host'
PY
g() { git -c safe.directory="$APP" -C "$APP" "$@"; }
[[ "$(g branch --show-current)" == main ]] || fail "Installed checkout must be main"
[[ -z "$(g status --porcelain)" ]] || fail "Installed checkout is dirty"
BASE="$(g rev-parse HEAD)"
[[ "$BASE" == "$EXPECTED_BASE" ]] || fail "Expected Release 642 baseline, found $BASE; recheck ancestry before qualifying"
g fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(g rev-parse "refs/remotes/origin/$REF")"
g merge-base --is-ancestor "$BASE" "$TARGET" || fail "Candidate is not descended from installed base"
RUN="$(mktemp -d /tmp/tracker-coa-qualification.XXXXXXXX)"
QA="$RUN/source"
cleanup() {
    if [[ -d "$QA" ]]; then g worktree remove --force "$QA" >/dev/null 2>&1 || true; fi
}
trap cleanup EXIT
g worktree add --detach "$QA" "$TARGET"
cd "$QA"
export TRACKER_DATA_DIR="$RUN/test-data" PYTHONPATH="$QA"
mkdir -p "$TRACKER_DATA_DIR"
echo "COA_BASE=$BASE"
echo "COA_CANDIDATE_COMMIT=$TARGET"
git diff --check "$BASE" "$TARGET"
"$PY" -m compileall -q app scripts tests/test_coa_multiple_documents.py
"$PY" - <<'PY'
from pathlib import Path
from jinja2 import Environment
env=Environment()
for name in ('coa_edit.html','coas.html'):
    env.parse((Path('app/templates')/name).read_text())
print('COA_JINJA=PASSED')
PY
"$PY" -m pytest -q --tb=short --maxfail=1 \
  tests/test_coa_multiple_documents.py \
  tests/test_coa_manager_v23.py \
  tests/test_coa_history_decimals_v23.py \
  tests/test_coa_migration_legacy.py \
  tests/test_attachment_scope396.py \
  tests/test_attachment_files400.py \
  tests/test_backup.py
echo "COA_SCOPED_QUALIFICATION=PASSED"
echo "COA_DEPLOYMENT=NOT_PERFORMED"
echo "COA_FULL_SUITE=NOT_RUN"
