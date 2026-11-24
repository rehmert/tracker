#!/usr/bin/env bash
# Release 769 guarded DEV-only install with verified pre-schema SQLite + upload snapshot.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
BASE=62a78b4f0b79f2f6762976c1231cab2f5f593f25
REF=release/769-google-tasks-medications-supplements-protocols
fail(){ echo "RELEASE_769_INSTALL_BLOCKED=$*" >&2; exit 1; }
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] || fail "Exact target required"
TARGET="$1"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] || fail "DEV only"
[[ -f /etc/tracker.env && -x "$APP/.venv/bin/python" ]] || fail "DEV missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main &&
 "$(git rev-parse HEAD)" == "$BASE" && -z "$(git status --porcelain)" ]] ||
 fail "Unexpected installed DEV baseline"
systemctl is-active --quiet tracker.service || fail "DEV service inactive"
git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
 fail "Release branch moved"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Non-descendant"
[[ -z "$(git diff --name-only "$BASE" "$TARGET" -- app/models.py app/migrations.py app/db.py requirements.txt)" ]] ||
 fail "Unexpected core schema or dependency changes"
STAGE="$(mktemp -d /tmp/tracker769-install.XXXXXXXX)"
trap 'rm -rf -- "$STAGE"' EXIT
RUNNER="$STAGE/runner.sh"
git show "$TARGET:scripts/tracker-release.sh" > "$RUNNER"
[[ "$(git hash-object "$RUNNER")" == "$(git rev-parse "$TARGET:scripts/tracker-release.sh")" ]] ||
 fail "Pinned runner checksum mismatch"
bash -n "$RUNNER"
# New separate additive ORM file is not matched by legacy runner schema guard.
# Preserve verified snapshot BEFORE first startup can create the four tables.
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
BACKUPS="$APP/backups/release769-preinstall"
mkdir -p -m 700 "$BACKUPS"
[[ ! -L "$BACKUPS" ]] || fail "Backup directory linked"
ARCHIVE="$(PYTHONPATH="$APP" "$APP/.venv/bin/python"  "$APP/scripts/tracker-workout-dev-backup655.py" --data "$DATA_DIR" --dest "$BACKUPS")" ||
 fail "Verified DEV backup failed"
[[ "$ARCHIVE" == "$BACKUPS"/tracker-dev655-*.zip && -s "$ARCHIVE" && ! -L "$ARCHIVE" ]] ||
 fail "Verified DEV archive missing"
echo "RELEASE_769_DEV_DB_SNAPSHOT=VERIFIED"
echo "RELEASE_769_PINNED_TARGET=$TARGET"
bash "$RUNNER" --instance DEV --base "$BASE" --target "$TARGET" --ref "$REF"
[[ "$(git branch --show-current)" == main &&
 "$(git rev-parse HEAD)" == "$TARGET" && -z "$(git status --porcelain)" ]] ||
 fail "Installed DEV SHA mismatch"
systemctl is-active --quiet tracker.service || fail "DEV service inactive after installation"
find "$BACKUPS" -maxdepth 1 -type f -name 'tracker-dev655-*.zip' -printf '%f\n' |
 sort -r | tail -n +11 | while IFS= read -r old; do rm -f -- "$BACKUPS/$old"; done
echo "RELEASE_769_DEV_INSTALL=SUCCESS"
