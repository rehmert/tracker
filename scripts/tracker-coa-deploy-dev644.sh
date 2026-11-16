#!/usr/bin/env bash
# Exact-commit DEV Release 644 deploy; guarded runner performs full promotion-readiness QA.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
REF=release/644-coa-csrf-inventory
BASE=c7335b409724999195364fa02ce344e41a5a0405
fail() { echo "COA_644_LAUNCH=FAILED: $*" >&2; exit 1; }
[[ "$(id -u)" == 0 && -x "$APP/.venv/bin/python" && -f /etc/tracker.env ]] || fail "Requires root and configured Tracker"
"$APP/.venv/bin/python" - <<'PY'
from pathlib import Path
import re
values=[]
for line in Path('/etc/tracker.env').read_text().splitlines():
 m=re.match(r'^\s*(?:export\s+)?TRACKER_INSTANCE\s*=(.*)$',line)
 if m: values.append(m.group(1).strip().strip(chr(34)).strip(chr(39)).upper())
assert values == ['DEV'], 'Refusing non-DEV host'
PY
g() { git -c safe.directory="$APP" -C "$APP" "$@"; }
[[ "$(g branch --show-current)" == main && -z "$(g status --porcelain)" ]] || fail "Expected clean DEV main"
[[ "$(g rev-parse HEAD)" == "$BASE" ]] || fail "Expected DEV installed 643"
systemctl is-active --quiet tracker || fail "DEV Tracker inactive"
g fetch origin main "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(g rev-parse "refs/remotes/origin/$REF")"
g merge-base --is-ancestor "$BASE" "$TARGET" || fail "Target not descended from DEV Release 643"
DIR="$(mktemp -d /tmp/tracker-coa644-runner.XXXXXXXX)"
cleanup() { rm -f "$DIR/runner.sh"; rmdir "$DIR" || true; }
trap cleanup EXIT
EXPECTED="$(g rev-parse "$TARGET:scripts/tracker-release.sh")"
g show "$TARGET:scripts/tracker-release.sh" > "$DIR/runner.sh"
[[ "$(g hash-object "$DIR/runner.sh")" == "$EXPECTED" ]] || fail "Pinned runner checksum mismatch"
bash -n "$DIR/runner.sh"
echo "COA_644_DEV_BASE=$BASE"
echo "COA_644_DEV_TARGET=$TARGET"
echo "COA_644_RUNNER_BLOB=$EXPECTED"
bash "$DIR/runner.sh" --instance DEV --base "$BASE" --target "$TARGET" --ref "$REF"
