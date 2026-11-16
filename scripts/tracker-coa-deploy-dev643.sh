#!/usr/bin/env bash
# Release 643: guarded DEV release launcher. Fetch exact target runner blob.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
REF=release/643-coa-multiple-documents
fail() { echo "COA_643_LAUNCH=FAILED: $*" >&2; exit 1; }
[[ "$(id -u)" == 0 && -x "$APP/.venv/bin/python" && -f /etc/tracker.env ]] || fail "Run as root on configured Tracker"
"$APP/.venv/bin/python" - <<'PY'
import re
from pathlib import Path
labels=[]
for line in Path('/etc/tracker.env').read_text().splitlines():
 m=re.match(r'^\s*(?:export\s+)?TRACKER_INSTANCE\s*=(.*)$',line)
 if m: labels.append(m.group(1).strip().strip(chr(34)).strip(chr(39)).upper())
assert labels == ['DEV'], 'Release 643 launcher is DEV-only'
PY
g() { git -c safe.directory="$APP" -C "$APP" "$@"; }
[[ "$(g branch --show-current)" == main ]] || fail "Expected main checkout"
[[ -z "$(g status --porcelain)" ]] || fail "Installed tree not clean"
systemctl is-active --quiet tracker || fail "Tracker must be running"
BASE="$(g rev-parse HEAD)"
g fetch origin main "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(g rev-parse "refs/remotes/origin/$REF")"
g merge-base --is-ancestor "$BASE" "$TARGET" || fail "Candidate not descended from installed DEV HEAD"
[[ "$BASE" != "$TARGET" ]] || fail "Already installed"
EXPECTED="$(g rev-parse "$TARGET:scripts/tracker-release.sh")"
[[ "$EXPECTED" =~ ^[0-9a-f]{40}$ ]] || fail "Candidate runner is missing"
DIR="$(mktemp -d /tmp/tracker-coa643-runner.XXXXXXXX)"
cleanup() { rm -f -- "$DIR/runner.sh"; rmdir -- "$DIR" || true; }
trap cleanup EXIT
g show "$TARGET:scripts/tracker-release.sh" > "$DIR/runner.sh"
[[ "$(g hash-object "$DIR/runner.sh")" == "$EXPECTED" ]] || fail "Runner blob verification failed"
bash -n "$DIR/runner.sh"
echo "COA_643_DEV_BASE=$BASE"
echo "COA_643_DEV_TARGET=$TARGET"
echo "COA_643_RUNNER_BLOB=$EXPECTED"
echo "COA_643_EXPECTED_SCOPE=DEV_ONLY"
bash "$DIR/runner.sh" \
 --instance DEV --base "$BASE" --target "$TARGET" \
 --ref "$REF" --db-migration --reviewed-coa-643
