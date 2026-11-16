#!/usr/bin/env bash
# Release 653: read-only isolated DEV preflight for the Manage COA Types UI.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
BASE=f342c81b32cf6a627b3958f45580315a08590a58
REF=release/653-coa-test-type-actions-row
fail() { echo "COA_653_PREFLIGHT=FAILED: $*" >&2; exit 1; }
[[ "$(id -u)" == 0 && -x "$PY" && -f /etc/tracker.env ]] ||
  fail "Run as root on configured Tracker DEV"
[[ "$(hostname -s)" == tracker-dev ]] ||
  fail "Expected tracker-dev host; no preflight performed"
g() { git -c safe.directory="$APP" -C "$APP" "$@"; }
[[ "$(g branch --show-current)" == main && -z "$(g status --porcelain)" ]] ||
  fail "Installed DEV checkout must be clean main"
[[ "$(g rev-parse HEAD)" == "$BASE" ]] || fail "DEV must be on Release 652"
systemctl is-active --quiet tracker || fail "Tracker DEV service inactive"
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] || fail "Pass exact candidate SHA"
EXPECTED="$1"
g fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(g rev-parse "refs/remotes/origin/$REF")"
[[ "$TARGET" == "$EXPECTED" ]] || fail "Release branch SHA changed"
g merge-base --is-ancestor "$BASE" "$TARGET" || fail "Release must descend from 652"
WORK="$(mktemp -d /tmp/tracker-coa653-preflight.XXXXXXXX)"
QA="$WORK/source"
cleanup() {
  if [[ -d "$QA" ]]; then g worktree remove --force "$QA" >/dev/null 2>&1 || true; fi
  rm -rf -- "$WORK"
}
trap cleanup EXIT
g worktree add --detach "$QA" "$TARGET"
"$PY" "$QA/scripts/tracker-instance-check653.py" --config /etc/tracker.env ||
  fail "DEV identity label verification failed; no deployment performed"
cd "$QA"
git diff --check "$BASE" "$TARGET"
echo "=== RELEASE 653 EXACT UI-ONLY CHANGE SCOPE ==="
"$PY" - "$BASE" "$TARGET" <<'PY'
from pathlib import Path
import subprocess, sys
base,target=sys.argv[1:]
allow={
    "app/templates/coa_test_types_manage652.html",
    "app/static/css/tracker-coa-type-actions653.css",
    "tests/test_coa_manage_actions653.py",
    "scripts/tracker-release-scoped653.sh",
    "scripts/tracker-coa-preflight653.sh",
    "scripts/tracker-coa-dev653.sh",
    "scripts/tracker-instance-check653.py",
    "tests/test_tracker_instance_check653.py",
    "scripts/tracker-release.sh",
}
files=set(subprocess.check_output(
    ["git", "diff", "--name-only", base, target], text=True
).splitlines())
assert files == allow, "Unreviewed UI release paths: " + repr(sorted(files ^ allow))
print("COA_653_UI_ONLY_SCOPE=PASSED")
PY
export PYTHONPATH="$QA" TRACKER_DATA_DIR="$WORK/test-data"
mkdir -p "$TRACKER_DATA_DIR"
for sh in scripts/tracker-release.sh scripts/tracker-release-scoped653.sh \
          scripts/tracker-coa-preflight653.sh scripts/tracker-coa-dev653.sh; do
  bash -n "$sh"
done
"$PY" -m py_compile tests/test_coa_manage_actions653.py
"$PY" - <<'PY'
from pathlib import Path
from jinja2 import Environment
Environment().parse(Path("app/templates/coa_test_types_manage652.html").read_text())
css=Path("app/static/css/tracker-coa-type-actions653.css").read_text()
assert "flex-wrap: nowrap" in css and "flex-direction: row" in css
assert ".coa-type-toggle-form653" in css
print("COA_653_TEMPLATE_AND_STYLESHEET=PASSED")
PY
"$PY" scripts/tracker-impact-preflight604.py --root "$QA" --base "$BASE" --target "$TARGET"
echo "=== RELEASE 653 CHANGE-SCOPED CHROMIUM UI TEST ==="
bash scripts/tracker-release-scoped653.sh "$PY"
echo "COA_653_PREFLIGHT=PASSED"
echo "COA_653_CANDIDATE=$TARGET"
echo "LIVE_DEV_SCHEMA=UNMODIFIED"
echo "DEPLOYMENT=NOT_PERFORMED"
