#!/usr/bin/env bash
# Release 650 DEV-only disposable worktree preflight. No deploy or migrations.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=2170ca0ab26b1fb5c4d7af506b499bde07e7048e
REF=release/650-coa-unified-documents
fail() { echo "COA_650_PREFLIGHT=FAILED: $*" >&2; exit 1; }
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
[[ "$(g rev-parse HEAD)" == "$BASE" ]] || fail "Installed DEV version is not Release 649"
g fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(g rev-parse "refs/remotes/origin/$REF")"
[[ "$#" == 1 && "$TARGET" == "$1" ]] || fail "Pass exact current candidate SHA"
RUN="$(mktemp -d /tmp/tracker-coa650-preflight.XXXXXXXX)"
QA="$RUN/source"
cleanup() { [[ ! -d "$QA" ]] || g worktree remove --force "$QA" >/dev/null 2>&1 || true; }
trap cleanup EXIT
g worktree add --detach "$QA" "$TARGET"
cd "$QA"
echo "=== DEV-ONLY ATTACHMENT AUDIT (NO PROD UPLOAD SYNCHRONIZATION) ==="
# On DEV only, report missing files without blocking isolated QA.
# Malformed paths or changed hashes of present files remain fatal.
"$PY" scripts/tracker-dev-attachment-gate650.py --data /opt/tracker/data ||
 fail "DEV integrity failure is not limited to unsynchronized missing files"
echo "COA_650_DEV_ATTACHMENTS=CHECKED_WITH_MISSING_FILE_POLICY"
export TRACKER_DATA_DIR="$RUN/test-data" PYTHONPATH="$QA"
mkdir -p "$TRACKER_DATA_DIR"
git diff --check "$BASE" "$TARGET"
# No schema change or bulk backfill: historic first files remain in the
# existing Coa fields until edited; the write path creates a regular attachment.
# Avoid PROD migration flags and any change to installed data in this preflight.
if git diff --name-only "$BASE" "$TARGET" | grep -Eq '^(app/(db|models|migrations)\.py|alembic/|scripts/.*(migrat|backfill|data[-_]fix))'; then
 fail "Release 650 must not change database or migration code"
fi
test -s app/static/css/tracker-coa-documents649.css
for script in scripts/tracker-release.sh scripts/tracker-coa-dev650.sh scripts/tracker-coa-scoped650.sh scripts/tracker-coa-preflight650.sh; do
  bash -n "$script"
done
"$PY" -m compileall -q app scripts tests/test_coa_unified_documents650.py tests/test_dev_attachment_gate650.py
node --check app/static/js/tracker-coa-types647.js
"$PY" - <<'PY'
from pathlib import Path
from jinja2 import Environment
for f in (Path("app/templates/base.html"), Path("app/templates/coa_edit.html")):
    Environment().parse(f.read_text())
print("COA_650_JINJA=PASSED")
PY
"$PY" scripts/tracker-impact-preflight604.py --root "$QA" --base "$BASE" --target "$TARGET"
# Exercise exactly the COA regression chain the DEV release worker will run,
# including strict-CSRF route inventory and reconciliation. This fails BEFORE
# any deployment, rather than discovering historical contract errors mid-run.
bash scripts/tracker-coa-scoped650.sh "$PY"
# A full DEV browser gate previously failed on stale historic COA link labels
# AFTER the backend-only preflight had passed. Re-run the existing isolated,
# strict, positive Chromium probes here; these are targeted diagnostics only,
# not a substitute for the full fifth-release DEV browser qualification.
echo "=== RELEASE 650 TARGETED STRICT COA BROWSER WITNESSES (DISPOSABLE) ==="
timeout 300 bash scripts/tracker-browser-qualify.sh "$QA" "$PY" --targeted-strict csrf-positive627
echo "COA_650_SIGNED_COA_BROWSER=PASSED"
timeout 240 bash scripts/tracker-browser-qualify.sh "$QA" "$PY" --targeted-strict tests/browser/test_csrf_multipart588.py
echo "COA_650_MULTIPART_COA_BROWSER=PASSED"
"$PY" -m pytest -q --tb=short --maxfail=1 \
 tests/test_release577_dev_receipt.py tests/test_release629_qa_cadence.py \
 tests/test_release604_preflight.py
echo "=== RELEASE 650 MILESTONE: FULL BACKEND QUALIFICATION ON ISOLATED DATA ==="
"$PY" -m pytest -n 16 --dist=loadfile -q --tb=short --disable-warnings --durations=15 tests \
  --ignore=tests/browser --ignore=tests/test_bulk_vial_browser.py \
  --ignore=tests/test_bulk_vial_guided_browser.py --ignore=tests/test_bulk_delete_browser.py \
  --ignore=tests/test_purchase_vial_browser.py --ignore=tests/test_stage33_browser_sorting.py \
  --ignore=tests/test_health_timeline_dates_browser.py --ignore=tests/test_vitals_csv_browser.py
echo "COA_650_FULL_BACKEND=PASSED"
echo "COA_650_PREFLIGHT=PASSED"
echo "COA_650_CANDIDATE=$TARGET"
echo "DEPLOYMENT=NOT_PERFORMED"
