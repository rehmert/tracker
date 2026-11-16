#!/usr/bin/env bash
# Guarded DEV Release 645 launcher, pinned to exact candidate Git object.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
REF=release/645-coa-default-document
BASE=5bc0894c2c2865856856298083ca21bc62d00069
fail() { echo "COA_645_DEPLOY=FAILED: $*" >&2; exit 1; }
[[ "$(id -u)" == 0 && -x "$APP/.venv/bin/python" && -f /etc/tracker.env ]] || fail "Requires configured Tracker and root"
"$APP/.venv/bin/python" - <<'PY'
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
[[ "$(g rev-parse HEAD)" == "$BASE" ]] || fail "Expected installed Release 644"
systemctl is-active --quiet tracker || fail "Tracker service inactive"
g fetch origin main "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(g rev-parse "refs/remotes/origin/$REF")"
g merge-base --is-ancestor "$BASE" "$TARGET" || fail "Target not descended from installed base"
DIR="$(mktemp -d /tmp/tracker-coa645-runner.XXXXXXXX)"
cleanup() { rm -f "$DIR/runner.sh"; rmdir "$DIR" || true; }
trap cleanup EXIT
EXPECTED="$(g rev-parse "$TARGET:scripts/tracker-release.sh")"
g show "$TARGET:scripts/tracker-release.sh" > "$DIR/runner.sh"
[[ "$(g hash-object "$DIR/runner.sh")" == "$EXPECTED" ]] || fail "Runner blob differs from pinned candidate"
bash -n "$DIR/runner.sh"
echo "COA_645_BASE=$BASE"
echo "COA_645_TARGET=$TARGET"
echo "COA_645_EXPECTED_SCOPE=DEV_ONLY"
bash "$DIR/runner.sh" \
 --instance DEV --base "$BASE" --target "$TARGET" \
 --ref "$REF" --db-migration --reviewed-coa-645
