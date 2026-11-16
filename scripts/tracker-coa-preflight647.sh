#!/usr/bin/env bash
# Release 647 DEV-only disposable worktree preflight. No deploy or migrations.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=61b3016eed48527c61a5173d94ee0f58b859f81a
REF=release/647-coa-bulk-test-types
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
[[ "$(g rev-parse HEAD)" == "$BASE" ]] || fail "Installed DEV version is not Release 646"
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
for script in scripts/tracker-release.sh scripts/tracker-coa-dev647.sh scripts/tracker-coa-scoped647.sh scripts/tracker-coa-preflight647.sh; do
  bash -n "$script"
done
"$PY" -m compileall -q app scripts tests/test_coa_bulk_test_types647.py
node --check app/static/js/tracker-coa-types647.js
"$PY" - <<'PY'
from pathlib import Path
from jinja2 import Environment
for f in (Path("app/templates/base.html"), Path("app/templates/coa_edit.html")):
    Environment().parse(f.read_text())
print("COA_647_JINJA=PASSED")
PY
"$PY" scripts/tracker-impact-preflight604.py --root "$QA" --base "$BASE" --target "$TARGET"
# Exercise exactly the COA regression chain the DEV release worker will run,
# including strict-CSRF route inventory and reconciliation. This fails BEFORE
# any deployment, rather than discovering historical contract errors mid-run.
bash scripts/tracker-coa-scoped647.sh "$PY"
"$PY" -m pytest -q --tb=short --maxfail=1 \
 tests/test_release577_dev_receipt.py tests/test_release629_qa_cadence.py \
 tests/test_release604_preflight.py
echo "COA_647_PREFLIGHT=PASSED"
echo "COA_647_CANDIDATE=$TARGET"
echo "DEPLOYMENT=NOT_PERFORMED"
