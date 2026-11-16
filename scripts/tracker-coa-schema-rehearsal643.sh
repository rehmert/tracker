#!/usr/bin/env bash
# DEV-only, non-deploying schema rehearsal with verified backup and disposable restore.
set -Eeuo pipefail
umask 077
APP=/opt/tracker
PY="$APP/.venv/bin/python"
REF=feature/coa-multiple-attachments
fail() { echo "COA_SCHEMA_REHEARSAL=FAILED: $*" >&2; exit 1; }
[[ "$(id -u)" == 0 && -x "$PY" && -f /etc/tracker.env ]] || fail "Requires root on configured Tracker DEV host"
"$PY" - <<'PY'
import re
from pathlib import Path
labels=[]
for line in Path('/etc/tracker.env').read_text().splitlines():
 m=re.match(r'^\s*(?:export\s+)?TRACKER_INSTANCE\s*=(.*)$',line)
 if m: labels.append(m.group(1).strip().strip(chr(34)).strip(chr(39)).upper())
assert labels == ['DEV'], 'Not a DEV instance'
PY
g() { git -c safe.directory="$APP" -C "$APP" "$@"; }
[[ "$(g branch --show-current)" == main && -z "$(g status --porcelain)" ]] || fail "Installed main must be clean"
BASE="$(g rev-parse HEAD)"
g fetch origin "refs/heads/$REF:refs/remotes/origin/$REF"
TARGET="$(g rev-parse "refs/remotes/origin/$REF")"
g merge-base --is-ancestor "$BASE" "$TARGET" || fail "Candidate is not descendant of installed base"
RUN="$(mktemp -d /tmp/tracker-coa-migration.XXXXXXXX)"
QA="$RUN/source"
cleanup() { [[ ! -d "$QA" ]] || g worktree remove --force "$QA" >/dev/null 2>&1 || true; }
trap cleanup EXIT
g worktree add --detach "$QA" "$TARGET"
echo "COA_SOURCE_COMMIT=$TARGET"
# Resolve the installed data directory using existing server configuration parsing.
DATA_DIR="$("$PY" - <<'PY'
from pathlib import Path
import re
root=Path('/opt/tracker'); data=root/'data'
for line in Path('/etc/tracker.env').read_text().splitlines():
 m=re.match(r'^\s*(?:export\s+)?TRACKER_DATA_DIR\s*=(.*)$',line)
 if m and m.group(1).strip(): data=Path(m.group(1).strip().strip(chr(34)).strip(chr(39)))
if not data.is_absolute(): data=root/'data'
print(data.resolve())
PY
)"
[[ -f "$DATA_DIR/tracker.db" ]] || fail "Live SQLite database missing"
# Backup is written to private rehearsal directory. This does not mutate installed database.
ARCHIVE="$(PYTHONPATH="$APP" TRACKER_DATA_DIR="$DATA_DIR" "$PY" - "$DATA_DIR" "$RUN" <<'PY'
from pathlib import Path
from app.backup import create_backup
import sys
print(create_backup(Path(sys.argv[1]),Path(sys.argv[2])))
PY
)"
[[ -f "$ARCHIVE" ]] || fail "Verified backup was not created"
PYTHONPATH="$APP" TRACKER_DATA_DIR="$DATA_DIR" "$PY" "$APP/scripts/tracker-restore-verify.py" --archive "$ARCHIVE"
echo "COA_PREMIGRATION_BACKUP=VERIFIED"
"$PY" - "$ARCHIVE" "$RUN" "$QA" <<'PY'
from pathlib import Path
import sys, zipfile, sqlite3
from sqlalchemy import create_engine, inspect
archive, run, qa = map(Path,sys.argv[1:])
# Only the verified DB snapshot is needed to validate the additive schema.
snapshot = run/'rehearsal.db'
with zipfile.ZipFile(archive) as z, snapshot.open('wb') as out:
    import shutil
    shutil.copyfileobj(z.open('tracker.db'),out)
sys.path.insert(0,str(qa))
from app.models import CoaAttachment
engine=create_engine('sqlite:///'+str(snapshot))
with engine.begin() as c:
    count_before=c.exec_driver_sql('SELECT count(*) FROM coas').scalar_one()
    existing=c.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table' AND name='coa_attachments'").first()
    if existing: raise RuntimeError('coa_attachments already exists in installed snapshot')
CoaAttachment.__table__.create(engine, checkfirst=False)
cols={c['name'] for c in inspect(engine).get_columns('coa_attachments')}
assert {'id','coa_id','test_type','stored_name','original_name','content_type','size_bytes','sha256','uploaded_at'}<=cols
with engine.begin() as c:
    assert c.exec_driver_sql('PRAGMA integrity_check').scalar_one()=='ok'
    assert c.exec_driver_sql('PRAGMA foreign_key_check').fetchall()==[]
    assert c.exec_driver_sql('SELECT count(*) FROM coas').scalar_one()==count_before
engine.dispose()
with sqlite3.connect(snapshot) as db:
    assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
print('COA_ADDITIVE_SCHEMA_ON_DISPOSABLE_RESTORE=PASSED')
PY
echo "COA_SCHEMA_REHEARSAL=PASSED"
echo "COA_LIVE_DB_MUTATION=NONE"
echo "COA_REHEARSAL_BACKUP=$ARCHIVE"
