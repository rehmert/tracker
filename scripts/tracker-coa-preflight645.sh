#!/usr/bin/env bash
# DEV-only Release 645 scoped preflight in disposable worktree (no deployment).
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
REF=release/645-coa-default-document
BASE=5bc0894c2c2865856856298083ca21bc62d00069
fail() { echo "COA_645_PREFLIGHT=FAILED: $*" >&2; exit 1; }
[[ "$(id -u)" == 0 && -x "$PY" && -f /etc/tracker.env ]] || fail "Requires root on configured DEV"
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
[[ "$(g branch --show-current)" == main && -z "$(g status --porcelain)" ]] || fail "Expected clean installed main"
[[ "$(g rev-parse HEAD)" == "$BASE" ]] || fail "Expected Release 644 installed"
g fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(g rev-parse "refs/remotes/origin/$REF")"
g merge-base --is-ancestor "$BASE" "$TARGET" || fail "Target not descended from Release 644"
RUN="$(mktemp -d /tmp/tracker-coa645-preflight.XXXXXXXX)"
QA="$RUN/source"
cleanup() { [[ ! -d "$QA" ]] || g worktree remove --force "$QA" >/dev/null 2>&1 || true; }
trap cleanup EXIT
g worktree add --detach "$QA" "$TARGET"
cd "$QA"
export TRACKER_DATA_DIR="$RUN/data" PYTHONPATH="$QA"
mkdir -p "$TRACKER_DATA_DIR"
git diff --check "$BASE" "$TARGET"
"$PY" -m compileall -q app scripts tests/test_coa_document_defaults645.py tests/test_coa_endotoxins645.py
bash -n scripts/tracker-release.sh scripts/tracker_prod_remote568.sh scripts/tracker-coa-dev645.sh
"$PY" scripts/tracker_schema_review645.py --root "$APP" --base "$BASE" --target "$TARGET"
"$PY" - <<'PY'
from pathlib import Path
from jinja2 import Environment
for name in ("coa_edit.html", "vial_detail.html"):
    Environment().parse((Path("app/templates") / name).read_text())
print("COA_645_TEMPLATE=PASSED")
PY
echo "=== RELEASE 645 BROWSER INVENTORY CONTRACT (FAIL FAST) ==="
"$PY" -m pytest -q --tb=short --maxfail=1 \
 tests/test_browser_qualification511.py::test_511_every_browser_module_in_disposable_qualification \
 tests/test_release627_csrf_reconciliation.py::test_627_release511_inventory_scopes_new_browser_modules_strict_only
echo "COA_645_BROWSER_INVENTORY=PASSED"
bash scripts/tracker-coa-scoped645.sh "$PY"
"$PY" -m pytest -q --tb=short --maxfail=1 \
 tests/test_release_workflow.py \
 tests/test_release604_preflight.py \
 tests/test_prod_parallel_release508.py \
 tests/test_test_benchmark.py \
 tests/test_release605_oom_guard.py
echo "=== TARGETED STRICT NOTES 580 BROWSER DIAGNOSTIC ==="
timeout 360 bash scripts/tracker-browser-qualify.sh "$QA" "$PY" --targeted-strict notes-lifecycle580
echo "COA_645_NOTES_BROWSER=PASSED"
echo "COA_645_PREFLIGHT=PASSED"
echo "COA_645_CANDIDATE=$TARGET"
echo "LIVE_DB=UNMODIFIED"
echo "DEPLOYMENT=NOT_PERFORMED"
