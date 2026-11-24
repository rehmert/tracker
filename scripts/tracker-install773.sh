#!/usr/bin/env bash
# Release 773: DEV-only guarded install; verified pre-schema SQLite + uploads backup.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
BASE=47642b465b1cb98f40aab2ce68c6a7526394298d
REF=release/773-google-tasks-custom-titles
PY="$APP/.venv/bin/python"
fail(){ echo "RELEASE_773_INSTALL_BLOCKED=$*" >&2; exit 1; }
[[ $# == 1 && "$1" =~ ^[0-9a-f]{40}$ ]] || fail "Exact target required"
TARGET="$1"
[[ "$(id -u)" == 0 && "$(hostname -s)" == tracker-dev ]] || fail "DEV only"
[[ -f /etc/tracker.env && -x "$PY" ]] || fail "DEV environment missing"
cd "$APP"
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=safe.directory GIT_CONFIG_VALUE_0="$APP"
[[ "$(git branch --show-current)" == main &&
 "$(git rev-parse HEAD)" == "$BASE" && -z "$(git status --porcelain)" ]] ||
 fail "Unexpected DEV baseline"
systemctl is-active --quiet tracker.service || fail "DEV Tracker inactive"
git fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
[[ "$(git rev-parse "refs/remotes/origin/$REF")" == "$TARGET" ]] ||
 fail "Pinned release SHA changed"
git merge-base --is-ancestor "$BASE" "$TARGET" || fail "Non-descendant target"
[[ -z "$(git diff --name-only "$BASE" "$TARGET" -- app/db.py app/models.py app/migrations.py app/main.py requirements.txt deploy/)" ]] ||
 fail "Unreviewed core schema or deployment change"
STAGE="$(mktemp -d /tmp/tracker773-install.XXXXXXXX)"
trap 'rm -rf -- "$STAGE"' EXIT
RUNNER="$STAGE/runner.sh"
GUARD="$STAGE/google-schema773.py"
for pair in "scripts/tracker-release.sh:$RUNNER" "scripts/tracker-prod-google-titles773.py:$GUARD"; do
 relative="${pair%%:*}"; destination="${pair#*:}"
 blob="$(git rev-parse "$TARGET:$relative")" || fail "Signed target missing $relative"
 [[ "$blob" =~ ^[0-9a-f]{40}$ ]] || fail "Invalid target Git object"
 git show "$TARGET:$relative" > "$destination" || fail "Unable to stage $relative"
 [[ -f "$destination" && ! -L "$destination" &&
    "$(git hash-object "$destination")" == "$blob" ]] ||
 fail "Pinned source integrity mismatch"
done
bash -n "$RUNNER"
# Verify the signed migration before any backup or live source changes.
DATA_DIR="$(PYTHONPATH="$APP" "$PY" -B - "$GUARD" "$APP" "$BASE" "$TARGET" <<'PYCODE'
import runpy
import sys
from pathlib import Path
guard = runpy.run_path(sys.argv[1])
app = Path(sys.argv[2])
guard["review_source"](app, sys.argv[3], sys.argv[4])
data = guard["resolve_data_dir"](app, Path("/etc/tracker.env"))
guard["verify_schema_before"](data)
print(data)
PYCODE
)" || fail "Signed exact schema review or DEV pre-schema inspection failed"
[[ -f "$DATA_DIR/tracker.db" && ! -L "$DATA_DIR/tracker.db" ]] ||
 fail "DEV database missing or linked"
BACKUPS="$APP/backups/release773-preinstall"
[[ ! -L "$BACKUPS" ]] || fail "Unsafe preinstall backup directory"
mkdir -p -m 700 "$BACKUPS"
chmod 700 "$BACKUPS"
ARCHIVE="$(PYTHONPATH="$APP" "$PY" -B "$APP/scripts/tracker-workout-dev-backup655.py" --data "$DATA_DIR" --dest "$BACKUPS")" ||
 fail "DEV database + present-upload snapshot and restore verification failed"
[[ "$ARCHIVE" == "$BACKUPS"/tracker-dev655-*.zip &&
 -s "$ARCHIVE" && ! -L "$ARCHIVE" ]] || fail "Verified backup file unavailable"
echo "RELEASE_773_DEV_SCHEMA_BACKUP=VERIFIED"
bash "$RUNNER" --instance DEV --base "$BASE" --target "$TARGET" --ref "$REF"
[[ "$(git branch --show-current)" == main &&
 "$(git rev-parse HEAD)" == "$TARGET" && -z "$(git status --porcelain)" ]] ||
 fail "Installed DEV SHA mismatch"
systemctl is-active --quiet tracker.service || fail "DEV service inactive after install"
find "$BACKUPS" -maxdepth 1 -type f -name 'tracker-dev655-*.zip' -printf '%f\n' |
 sort -r | tail -n +11 | while IFS= read -r old; do rm -f -- "$BACKUPS/$old"; done
echo "RELEASE_773_DEV_INSTALL=SUCCESS"
