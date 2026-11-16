#!/usr/bin/env bash
# Additive, one-way PROD->DEV upload reconciliation. No DB copy or deletion.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
SOURCE="$PROD_SSH"
fail() { echo "UPLOAD_REPLICATION=FAILED: $*" >&2; exit 1; }
[[ "$(id -u)" == 0 && -x "$PY" && -f /etc/tracker.env ]] ||
 fail "Run as root on configured Tracker DEV"
[[ "$SOURCE" =~ ^[a-zA-Z_][a-zA-Z0-9_-]*@[a-zA-Z0-9][a-zA-Z0-9.-]*$ ]] ||
 fail "Invalid PROD_SSH (expected user@hostname)"
CONFIG="$("$PY" - <<'PY'
from pathlib import Path
import re
items={}
for line in Path("/etc/tracker.env").read_text().splitlines():
    m=re.match(r'^\s*(?:export\s+)?(TRACKER_INSTANCE|TRACKER_DATA_DIR)\s*=(.*)$', line)
    if m: items[m.group(1)]=m.group(2).strip().strip(chr(34)).strip(chr(39))
print(items.get("TRACKER_INSTANCE","").upper())
print(items.get("TRACKER_DATA_DIR","/opt/tracker/data"))
PY
)"
[[ "$CONFIG" == $'DEV\n/opt/tracker/data' ]] || fail "DEV-only and default data directory required"
command -v rsync >/dev/null || fail "rsync required on DEV and PROD"
exec 9>/run/lock/tracker-db-sync.lock
flock -n 9 || fail "Database replication or deployment currently active"
ssh -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=yes "$SOURCE" \
 'test -f /opt/tracker/data/tracker.db && test -d /opt/tracker/data/uploads && command -v rsync >/dev/null && grep -Eq "^[[:space:]]*(export[[:space:]]+)?TRACKER_INSTANCE=[[:space:]]*PROD[[:space:]]*$" /etc/tracker.env' ||
 fail "PROD identity, access, or upload source not verified"
echo "UPLOAD_REPLICATION_SOURCE=$SOURCE"
echo "UPLOAD_REPLICATION_DESTINATION=/opt/tracker/data/uploads"
# --ignore-existing never replaces DEV-only files; no --delete.
rsync -rt --ignore-existing --omit-dir-times --no-owner --no-group \
 --chmod=F644,D755 \
 -e 'ssh -o BatchMode=yes -o StrictHostKeyChecking=yes' \
 "$SOURCE:/opt/tracker/data/uploads/" "/opt/tracker/data/uploads/" ||
 fail "Additive PROD upload transfer failed"
# Stage a copy of the verifier at its exact candidate source, rather than
# assuming the pending release's code has been installed yet.
if [[ -f "$APP/scripts/tracker-attachment-integrity645.py" ]]; then
 "$PY" "$APP/scripts/tracker-attachment-integrity645.py" \
 --data "/opt/tracker/data" --hashes ||
 fail "Some DEV DB references remain unresolved"
else
 echo "UPLOAD_REPLICATION=TRANSFER_COMPLETE; run candidate attachment integrity gate"
fi
echo "PROD_DATABASE=UNMODIFIED"
echo "DEV_DATABASE=UNMODIFIED"
echo "EXISTING_DEV_UPLOADS=NOT_OVERWRITTEN"
echo "DELETE=NONE"
