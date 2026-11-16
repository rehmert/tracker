#!/usr/bin/env bash
# Release 647 DEV-only disposable worktree preflight. No deploy or migrations.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=9305aae5df5ca24afcf9735d73d914a918adcafb
REF=release/647-coa-test-type-picker
fail() { echo "COA_647_PREFLIGHT=FAILED: $*" >&2; exit 1; }
[[ "$(id -u)" == 0 && -x "$PY" && -f /etc/tracker.env ]] || fail "Run on configured DEV as root"
"$PY" - <<'PY'
from pathlib import Path
import re
labels=[]
for line in Path("/etc/tracker.env").read_text().splitlines():
 m=re.match(r'^\s*(?:export\s+)?TRACKER_INSTANCE\s*=(.*)$',line)
 if m: labels.append(m.group(1).strip().strip(chr(34)).strip(chr(39)).upper())
assert labels == ["DEV"], "DEV-only"
PY
g() { git -c safe.directory="$APP" -C "$APP" "$@"; }
[[ "$(g branch --show-current)" == main && -z "$(g status --porcelain)" ]] || fail "DEV checkout not clean main"
[[ "$(g rev-parse HEAD)" == "$BASE" ]] || fail "Installed DEV version is not Release 645"
g fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(g rev-parse "refs/remotes/origin/$REF")"
[[ "$#" == 1 && "$TARGET" == "$1" ]] || fail "Pass exact current candidate SHA"
RUN="$(mktemp -d /tmp/tracker-coa647-preflight.XXXXXXXX)"
QA="$RUN/source"
cleanup() { [[ ! -d "$QA" ]] || g worktree remove --force "$QA" >/dev/null 2>&1 || true; }
trap cleanup EXIT
g worktree add --detach "$QA" "$TARGET"
cd "$QA"
echo "=== LIVE ATTACHMENT INTEGRITY (BEFORE TESTS) ==="
"$PY" scripts/tracker-attachment-integrity645.py --data /opt/tracker/data --hashes ||
 fail "Missing live attachments: reconcile before qualification"
echo "COA_647_LIVE_ATTACHMENTS=PASSED"
export TRACKER_DATA_DIR="$RUN/test-data" PYTHONPATH="$QA"
mkdir -p "$TRACKER_DATA_DIR"
git diff --check "$BASE" "$TARGET"
bash -n scripts/tracker-release.sh scripts/tracker-coa-dev647.sh scripts/tracker-coa-scoped647.sh
"$PY" -m compileall -q app scripts tests/test_coa_test_type_picker647.py
node --check app/static/js/tracker-coa-types647.js
"$PY" - <<'PY'
from pathlib import Path
from jinja2 import Environment
for f in (Path("app/templates/base.html"), Path("app/templates/coa_edit.html")):
    Environment().parse(f.read_text())
print("COA_647_JINJA=PASSED")
PY
"$PY" scripts/tracker-impact-preflight604.py --root "$QA" --base "$BASE" --target "$TARGET"
bash scripts/tracker-coa-scoped647.sh "$PY"
"$PY" -m pytest -q --tb=short --maxfail=1 \
 tests/test_release577_dev_receipt.py tests/test_release629_qa_cadence.py \
 tests/test_release604_preflight.py
echo "COA_647_PREFLIGHT=PASSED"
echo "COA_647_CANDIDATE=$TARGET"
echo "DEPLOYMENT=NOT_PERFORMED"
