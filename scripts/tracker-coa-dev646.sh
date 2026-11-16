#!/usr/bin/env bash
# Pin a scoped Release 646 DEV deploy to an exact committed Git object.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
BASE=9305aae5df5ca24afcf9735d73d914a918adcafb
REF=release/646-coa-test-type-picker
fail() { echo "COA_646_DEV=FAILED: $*" >&2; exit 1; }
[[ "$#" == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] || fail "Pass exact candidate SHA"
EXPECTED_TARGET="$1"
[[ "$(id -u)" == 0 && -x "$APP/.venv/bin/python" ]] || fail "Run as root on configured DEV"
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
[[ "$(g branch --show-current)" == main && -z "$(g status --porcelain)" ]] ||
 fail "Installed DEV checkout not clean main"
[[ "$(g rev-parse HEAD)" == "$BASE" ]] || fail "DEV starting commit is not Release 645"
systemctl is-active --quiet tracker || fail "DEV service inactive"
g fetch origin main "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(g rev-parse "refs/remotes/origin/$REF")"
[[ "$TARGET" == "$EXPECTED_TARGET" ]] || fail "Release branch moved past pinned SHA"
g merge-base --is-ancestor "$BASE" "$TARGET" || fail "Target not descendant of installed base"
TMP="$(mktemp -d /tmp/tracker-coa646-runner.XXXXXXXX)"
cleanup() { rm -f "$TMP/runner.sh"; rmdir "$TMP" || true; }
trap cleanup EXIT
EXPECTED_BLOB="$(g rev-parse "$TARGET:scripts/tracker-release.sh")"
g show "$TARGET:scripts/tracker-release.sh" > "$TMP/runner.sh"
[[ "$(g hash-object "$TMP/runner.sh")" == "$EXPECTED_BLOB" ]] || fail "Runner does not match exact Git blob"
bash -n "$TMP/runner.sh"
echo "COA_646_TARGET=$TARGET"
echo "COA_646_TEST_MODE=CHANGE_SCOPED"
bash "$TMP/runner.sh" --instance DEV --base "$BASE" --target "$TARGET" --ref "$REF"
