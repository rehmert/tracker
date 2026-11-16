#!/usr/bin/env bash
# Release 652: preflight on tracker-dev; isolated worktree and data only.
# Does NOT modify the installed source, production, or live DEV schema.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=a9d45b7104313e9821b4f41db792e657c2de90b3
REF=release/652-coa-test-type-catalog
fail() { echo "COA_652_PREFLIGHT=FAILED: $*" >&2; exit 1; }
[[ "$(id -u)" == 0 && -x "$PY" && -f /etc/tracker.env ]] || fail "Run as root on configured DEV"
"$PY" - <<'PY'
from pathlib import Path
import re
values=[]
for line in Path("/etc/tracker.env").read_text().splitlines():
 m=re.match(r'^\s*(?:export\s+)?TRACKER_INSTANCE\s*=(.*)$',line)
 if m: values.append(m.group(1).strip().strip(chr(34)).strip(chr(39)).upper())
assert values == ["DEV"], "DEV only"
PY
g() { git -c safe.directory="$APP" -C "$APP" "$@"; }
[[ "$(g branch --show-current)" == main && -z "$(g status --porcelain)" ]] ||
 fail "Installed DEV checkout must be clean main"
[[ "$(g rev-parse HEAD)" == "$BASE" ]] || fail "DEV must still be Release 651"
systemctl is-active --quiet tracker || fail "DEV Tracker service inactive"
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] || fail "Pass exact candidate SHA"
EXPECTED="$1"
g fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(g rev-parse "refs/remotes/origin/$REF")"
[[ "$TARGET" == "$EXPECTED" ]] || fail "Release branch SHA moved"
g merge-base --is-ancestor "$BASE" "$TARGET" || fail "Candidate not descended from Release 651"
RUN="$(mktemp -d /tmp/tracker-coa652-preflight.XXXXXXXX)"
QA="$RUN/source"
cleanup() { [[ ! -d "$QA" ]] || g worktree remove --force "$QA" >/dev/null 2>&1 || true; }
trap cleanup EXIT
g worktree add --detach "$QA" "$TARGET"
cd "$QA"
git diff --check "$BASE" "$TARGET"
echo "=== RELEASE 652 EXACT ADDITIVE SCHEMA REVIEW ==="
"$PY" scripts/tracker_schema_review652.py --root "$APP" --base "$BASE" --target "$TARGET"
# Schema-changing releases are migration-backed and do not waive attachment
# integrity. Fail before lengthy QA if linked files are missing or modified.
echo "=== RELEASE 652 STRICT DEV ATTACHMENT PREFLIGHT ==="
"$PY" scripts/tracker-attachment-integrity645.py --data /opt/tracker/data --hashes ||
 fail "DEV attachment integrity must be reconciled before any schema deployment"
export TRACKER_DATA_DIR="$RUN/test-data" PYTHONPATH="$QA"
mkdir -p "$TRACKER_DATA_DIR"
for sh in scripts/tracker-release.sh scripts/tracker-coa-preflight652.sh \
          scripts/tracker-coa-dev652.sh scripts/tracker-coa-scoped652.sh; do
 bash -n "$sh"
done
"$PY" -m compileall -q app scripts tests/test_coa_manage_catalog652.py
node --check app/static/js/tracker-coa-multi651.js
"$PY" - <<'PY'
from pathlib import Path
from jinja2 import Environment
for name in ("coa_test_types_manage652.html", "coa_edit.html", "coas.html"):
    Environment().parse((Path("app/templates") / name).read_text())
print("COA_652_TEMPLATE_SYNTAX=PASSED")
PY
"$PY" scripts/tracker-impact-preflight604.py --root "$QA" --base "$BASE" --target "$TARGET"
bash scripts/tracker-coa-scoped652.sh "$PY"
# Existing strict browser checks cover the shared COA multipart/origin path.
timeout 300 bash scripts/tracker-browser-qualify.sh "$QA" "$PY" --targeted-strict csrf-positive627
timeout 240 bash scripts/tracker-browser-qualify.sh "$QA" "$PY" --targeted-strict tests/browser/test_csrf_multipart588.py
echo "COA_652_TARGETED_CSRF_BROWSER=PASSED"
echo "COA_652_PREFLIGHT=PASSED"
echo "COA_652_CANDIDATE=$TARGET"
echo "LIVE_DEV_SCHEMA=UNMODIFIED"
echo "DEPLOYMENT=NOT_PERFORMED"
