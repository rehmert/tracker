#!/usr/bin/env bash
# Release 649 DEV-only disposable worktree preflight. No deploy or migrations.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=0cc24c99955791a1843431b4b0bcd47a453c70bc
REF=release/649-coa-documents-audit-ui
fail() { echo "COA_649_PREFLIGHT=FAILED: $*" >&2; exit 1; }
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
[[ "$(g rev-parse HEAD)" == "$BASE" ]] || fail "Installed DEV version is not Release 648"
g fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(g rev-parse "refs/remotes/origin/$REF")"
[[ "$#" == 1 && "$TARGET" == "$1" ]] || fail "Pass exact current candidate SHA"
RUN="$(mktemp -d /tmp/tracker-coa649-preflight.XXXXXXXX)"
QA="$RUN/source"
cleanup() { [[ ! -d "$QA" ]] || g worktree remove --force "$QA" >/dev/null 2>&1 || true; }
trap cleanup EXIT
g worktree add --detach "$QA" "$TARGET"
cd "$QA"
echo "=== LIVE ATTACHMENT INTEGRITY (BEFORE TESTS) ==="
"$PY" scripts/tracker-attachment-integrity645.py --data /opt/tracker/data --hashes ||
 fail "Missing live attachments: reconcile before qualification"
echo "COA_649_LIVE_ATTACHMENTS=PASSED"
export TRACKER_DATA_DIR="$RUN/test-data" PYTHONPATH="$QA"
mkdir -p "$TRACKER_DATA_DIR"
git diff --check "$BASE" "$TARGET"
# The legacy Original document remains in coa metadata and attachments keep
# their existing records; this UI change must not introduce migrations.
if git diff --name-only "$BASE" "$TARGET" | grep -Eq '^(app/(db|models|migrations)\.py|alembic/|scripts/.*(migrat|backfill|data[-_]fix))'; then
 fail "Release 649 must not change database or migration code"
fi
test -s app/static/css/tracker-coa-documents649.css
for script in scripts/tracker-release.sh scripts/tracker-coa-dev649.sh scripts/tracker-coa-scoped649.sh scripts/tracker-coa-preflight649.sh; do
  bash -n "$script"
done
"$PY" -m compileall -q app scripts tests/test_coa_documents_ui649.py
node --check app/static/js/tracker-coa-types647.js
"$PY" - <<'PY'
from pathlib import Path
from jinja2 import Environment
for f in (Path("app/templates/base.html"), Path("app/templates/coa_edit.html")):
    Environment().parse(f.read_text())
print("COA_649_JINJA=PASSED")
PY
"$PY" scripts/tracker-impact-preflight604.py --root "$QA" --base "$BASE" --target "$TARGET"
# Exercise exactly the COA regression chain the DEV release worker will run,
# including strict-CSRF route inventory and reconciliation. This fails BEFORE
# any deployment, rather than discovering historical contract errors mid-run.
bash scripts/tracker-coa-scoped649.sh "$PY"
"$PY" -m pytest -q --tb=short --maxfail=1 \
 tests/test_release577_dev_receipt.py tests/test_release629_qa_cadence.py \
 tests/test_release604_preflight.py
echo "COA_649_PREFLIGHT=PASSED"
echo "COA_649_CANDIDATE=$TARGET"
echo "DEPLOYMENT=NOT_PERFORMED"
