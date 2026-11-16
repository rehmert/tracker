#!/usr/bin/env bash
# Release 644 DEV-only disposable preflight. Never installs/deploys or promotes.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
REF=release/644-coa-csrf-inventory
BASE_642=92f6193f509abcb12fd4c9a2f4c8d11854822044
BASE_643=c7335b409724999195364fa02ce344e41a5a0405
fail() { echo "COA_644_PREFLIGHT=FAILED: $*" >&2; exit 1; }
[[ "$(id -u)" == 0 && -x "$PY" && -f /etc/tracker.env ]] || fail "Requires root on configured Tracker"
"$PY" - <<'PY'
import re
from pathlib import Path
values=[]
for line in Path("/etc/tracker.env").read_text().splitlines():
 match=re.match(r'^\s*(?:export\s+)?TRACKER_INSTANCE\s*=(.*)$',line)
 if match: values.append(match.group(1).strip().strip(chr(34)).strip(chr(39)).upper())
assert values == ["DEV"], "Refusing non-DEV host"
PY
g() { git -c safe.directory="$APP" -C "$APP" "$@"; }
[[ "$(g branch --show-current)" == main && -z "$(g status --porcelain)" ]] || fail "Expected clean installed main"
[[ "$(g rev-parse HEAD)" == "$BASE_643" ]] || fail "Expected qualified DEV Release 643"
g fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(g rev-parse "refs/remotes/origin/$REF")"
g merge-base --is-ancestor "$BASE_643" "$TARGET" || fail "Candidate not descendant of DEV 643"
RUN="$(mktemp -d /tmp/tracker-coa644-preflight.XXXXXXXX)"
QA="$RUN/source"
cleanup() { [[ ! -d "$QA" ]] || g worktree remove --force "$QA" >/dev/null 2>&1 || true; }
trap cleanup EXIT
g worktree add --detach "$QA" "$TARGET"
cd "$QA"
export PYTHONPATH="$QA" TRACKER_DATA_DIR="$RUN/data"
mkdir -p "$TRACKER_DATA_DIR"
git diff --check "$BASE_643" "$TARGET"
"$PY" -m compileall -q app scripts tests/test_release627_csrf_remaining_negative_matrix.py
bash -n scripts/tracker-release.sh scripts/tracker_prod_remote568.sh scripts/tracker-coa-deploy-dev644.sh
"$PY" scripts/tracker_schema_review643.py --root "$APP" --base "$BASE_642" --target "$TARGET"
"$PY" -m pytest -q --tb=short --maxfail=1 \
 tests/test_release627_csrf_remaining_negative_matrix.py \
 tests/test_release627_csrf_reconciliation.py \
 tests/test_release597_purchase_supply_csrf.py \
 tests/test_release574_csrf_dynamic_shapes.py \
 tests/test_release596_vendor_multipart_csv.py \
 tests/test_release593_pk_final_witnesses.py \
 tests/test_release594_food_vendor_csrf.py \
 tests/test_release595_food_vendor_lifecycle.py \
 tests/test_coa_multiple_documents.py \
 tests/test_attachment_scope396.py \
 tests/test_release_workflow.py \
 tests/test_release604_preflight.py \
 tests/test_test_benchmark.py \
 tests/test_prod_parallel_release508.py
echo "COA_644_SCOPED_PREFLIGHT=PASSED"
echo "COA_644_CANDIDATE=$TARGET"
echo "LIVE_DB=UNMODIFIED"
echo "INSTALLATION=NOT_PERFORMED"
