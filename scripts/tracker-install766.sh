#!/usr/bin/env bash
# Release 766 guarded DEV install, with private verified schema-introduction snapshot.
# Invoked only after immutable passed qualification; the agent still owns all
# stage authorization, exact commit checks, release runner and live install.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
BASE=8c67580611fd945d9ae83f8015f071a24ab6fee5
REF=release/766-mobile-recipes-device-trends
fail(){ echo "RELEASE_766_INSTALL_BLOCKED=$*" >&2; exit 1; }
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] || fail "Exact pinned SHA required"
TARGET="$1"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] || fail "DEV only"
[[ -f /etc/tracker.env && -x "$APP/.venv/bin/python" ]] || fail "DEV missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory
export GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main &&
 "$(git rev-parse HEAD)" == "$BASE" && -z "$(git status --porcelain)" ]] ||
 fail "Unexpected DEV Release 765 installed baseline"
systemctl is-active --quiet tracker.service || fail "DEV service inactive"
git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
 fail "Release branch moved"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Not a descendant of DEV base"
STAGE="$(mktemp -d /tmp/tracker766-install.XXXXXXXX)"
trap 'rm -rf -- "$STAGE"' EXIT
RUNNER="$STAGE/runner.sh"
git show "$TARGET:scripts/tracker-release.sh" > "$RUNNER"
[[ "$(git hash-object "$RUNNER")" == "$(git rev-parse "$TARGET:scripts/tracker-release.sh")" ]] ||
 fail "Pinned release runner integrity mismatch"
bash -n "$RUNNER"
# A new independent model module (device_models766) is not yet included in
# the runner's schema diff matcher. Preserve independently verified
# database+attachment snapshot before any additive table is registered.
# Compensate
# with a separately verified DEV-only backup BEFORE invoking the guarded
# runner. This extra backup is not permission for or a substitute for PROD
# migration preflight and authorization.
DATA_DIR="$("$APP/.venv/bin/python" - <<'PYCODE'
from pathlib import Path
import re
root=Path('/opt/tracker'); data=root/'data'
for line in Path('/etc/tracker.env').read_text().splitlines():
 m=re.match(r'^\s*(?:export\s+)?TRACKER_DATA_DIR\s*=(.*)$',line)
 if m and m.group(1).strip(): data=Path(m.group(1).strip().strip("\"'"))
if not data.is_absolute(): data=root/data
print(data.resolve())
PYCODE
)"
[[ -f "$DATA_DIR/tracker.db" && ! -L "$DATA_DIR/tracker.db" ]] ||
 fail "DEV database missing or linked"
BACKUPS="$APP/backups/release766-preinstall"
mkdir -p -m 700 "$BACKUPS"
[[ ! -L "$BACKUPS" ]] || fail "Backup location is linked"
HELPER="$STAGE/dev-backup655.py"
git show "$TARGET:scripts/tracker-workout-dev-backup655.py" > "$HELPER"
# The backup helper locates its adjacent trusted 650 script at import time,
# so run the reviewed source path from the unchanged installed checkout.
# The helper itself verifies database consistency and restore integrity.
ARCHIVE="$(PYTHONPATH="$APP" "$APP/.venv/bin/python" \
 "$APP/scripts/tracker-workout-dev-backup655.py" --data "$DATA_DIR" --dest "$BACKUPS")" ||
 fail "Verified DEV snapshot failed"
[[ "$ARCHIVE" == "$BACKUPS"/tracker-dev655-*.zip && -s "$ARCHIVE" && ! -L "$ARCHIVE" ]] ||
 fail "DEV snapshot evidence missing"
echo "RELEASE_766_DEV_DB_SNAPSHOT=VERIFIED"
echo "RELEASE_766_PINNED_TARGET=$TARGET"
bash "$RUNNER" --instance DEV --base "$BASE" --target "$TARGET" --ref "$REF"
[[ "$(git branch --show-current)" == main &&
 "$(git rev-parse HEAD)" == "$TARGET" &&
 -z "$(git status --porcelain)" ]] || fail "Installed DEV commit mismatch"
systemctl is-active --quiet tracker.service || fail "DEV service not active after install"
# Preserve ten newest RELEASE-766 private snapshots; do not delete ordinary
# Tracker backup archives or touch production backups.
find "$BACKUPS" -maxdepth 1 -type f -name 'tracker-dev655-*.zip' -printf '%f\n' |
 sort -r | tail -n +11 | while IFS= read -r old; do rm -f -- "$BACKUPS/$old"; done
echo "RELEASE_766_DEV_INSTALL=SUCCESS"
