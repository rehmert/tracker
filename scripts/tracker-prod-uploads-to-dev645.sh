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
# Resolve the configured path rather than comparing raw strings (trailing /,
# quoted values and equivalent absolute paths must not cause false failures).
"$PY" - <<'PY'
from pathlib import Path
import re
values = {}
for line in Path("/etc/tracker.env").read_text().splitlines():
    m = re.match(r'^\s*(?:export\s+)?(TRACKER_INSTANCE|TRACKER_DATA_DIR)\s*=(.*)$', line)
    if m:
        values.setdefault(m.group(1), []).append(m.group(2).strip().strip("\"'"))
labels = values.get("TRACKER_INSTANCE", [])
data = values.get("TRACKER_DATA_DIR", ["/opt/tracker/data"])
if len(labels) != 1 or labels[0].upper() != "DEV":
    raise SystemExit(f"UPLOAD_REPLICATION=FAILED: expected DEV instance label, got {labels!r}")
if len(data) != 1 or not data[0]:
    raise SystemExit("UPLOAD_REPLICATION=FAILED: ambiguous data path")
resolved = Path(data[0]).resolve()
expected = Path("/opt/tracker/data").resolve()
if resolved != expected:
    raise SystemExit(f"UPLOAD_REPLICATION=FAILED: data path {resolved} differs from expected {expected}")
print(f"UPLOAD_REPLICATION_DEV_DATA={resolved}")
PY
command -v rsync >/dev/null || fail "rsync required on DEV and PROD"
exec 9>/run/lock/tracker-db-sync.lock
flock -n 9 || fail "Database replication or deployment currently active"
# Verify the actual PROD label and canonical data path, including quoted values.
if ! ssh -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=yes "$SOURCE" \
 'python3 -' <<'PY'
from pathlib import Path
import re
import shutil

values = {}
for line in Path("/etc/tracker.env").read_text().splitlines():
    m = re.match(r'^\s*(?:export\s+)?(TRACKER_INSTANCE|TRACKER_DATA_DIR)\s*=(.*)$', line)
    if m:
        values.setdefault(m.group(1), []).append(m.group(2).strip().strip("\"'"))
labels = values.get("TRACKER_INSTANCE", [])
roots = values.get("TRACKER_DATA_DIR", ["/opt/tracker/data"])
if len(labels) != 1 or labels[0].upper() != "PROD":
    raise SystemExit("UPLOAD_REPLICATION=FAILED: remote instance is not explicitly PROD")
if len(roots) != 1 or not roots[0] or Path(roots[0]).resolve() != Path("/opt/tracker/data").resolve():
    raise SystemExit("UPLOAD_REPLICATION=FAILED: remote data directory mismatch")
if not Path("/opt/tracker/data/tracker.db").is_file():
    raise SystemExit("UPLOAD_REPLICATION=FAILED: PROD database absent")
if not Path("/opt/tracker/data/uploads").is_dir() or not shutil.which("rsync"):
    raise SystemExit("UPLOAD_REPLICATION=FAILED: remote uploads or rsync unavailable")
print("UPLOAD_REPLICATION_REMOTE_IDENTITY=PROD_VERIFIED")
PY
then
 fail "PROD identity, access, or upload source not verified"
fi
echo "UPLOAD_REPLICATION_SOURCE=$SOURCE"
echo "UPLOAD_REPLICATION_DESTINATION=/opt/tracker/data/uploads"
# --ignore-existing never replaces DEV-only files; no --delete.
rsync -rt --ignore-existing --omit-dir-times --no-owner --no-group \
 --chmod=F644,D755 \
 -e 'ssh -o BatchMode=yes -o StrictHostKeyChecking=yes' \
 "$SOURCE:/opt/tracker/data/uploads/" "/opt/tracker/data/uploads/" ||
 fail "Additive PROD upload transfer failed"
"$PY" - <<'PY'
import hashlib
import sqlite3
from pathlib import Path
root=Path("/opt/tracker/data")
missing=[]
bad_hash=[]
with sqlite3.connect(f"file:{root / 'tracker.db'}?mode=ro", uri=True) as db:
    db.execute("PRAGMA query_only=ON")
    for table,folder in (("coas","coa"),("coa_attachments","coa"),("lab_reports","labs")):
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(table,)).fetchone(): continue
        cols={r[1] for r in db.execute(f'PRAGMA table_info("{table}")')}
        if not {"id","stored_name","original_name"} <= cols: continue
        sql=f'SELECT id,stored_name,original_name,{"sha256" if "sha256" in cols else "NULL"} FROM "{table}"'
        for ident,stored,original,expected in db.execute(sql):
            if not original: continue
            if not stored or "/" in stored or "\\" in stored or stored in (".",".."):
                missing.append((table,ident)); continue
            file=root/"uploads"/folder/stored
            if file.is_symlink() or not file.is_file():
                missing.append((table,ident)); continue
            if expected:
                with file.open("rb") as fh:
                    actual=hashlib.file_digest(fh,"sha256").hexdigest()
                if actual.lower()!=expected.lower(): bad_hash.append((table,ident))
print(f"UPLOAD_REPLICATION_MISSING={len(missing)}")
print(f"UPLOAD_REPLICATION_HASH_MISMATCH={len(bad_hash)}")
for table,ident in missing: print(f"MISSING table={table} id={ident}")
for table,ident in bad_hash: print(f"HASH_MISMATCH table={table} id={ident}")
if missing or bad_hash: raise SystemExit("UPLOAD_REPLICATION=INCOMPLETE")
print("UPLOAD_REPLICATION=PASSED")
PY
echo "PROD_DATABASE=UNMODIFIED"
echo "DEV_DATABASE=UNMODIFIED"
echo "EXISTING_DEV_UPLOADS=NOT_OVERWRITTEN"
echo "DELETE=NONE"
