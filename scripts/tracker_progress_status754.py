#!/usr/bin/env python3
"""Read one root-private export status file, calculating staleness at read time."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import stat
import sys

def report(path, now=None):
    path=Path(path).absolute()
    if path.is_symlink() or not path.is_file():
        return "MISSING"
    st=path.stat()
    if st.st_uid != os.geteuid() or st.st_mode & 0o077 or not stat.S_ISREG(st.st_mode):
        return "UNTRUSTED_STATUS"
    try:
        doc=json.loads(path.read_text())
        outcome=doc.get("status")
        if outcome not in ("successful","failed","local_validated"):
            return "INVALID_STATUS"
        last=doc.get("last_success_utc")
        if outcome=="local_validated":
            return "LOCAL_VALIDATED_NOT_SYNCED"
        if not isinstance(last,str):
            return "FAILED_NEVER_SYNCED" if outcome=="failed" else "INVALID_STATUS"
        when=datetime.fromisoformat(last.replace("Z","+00:00"))
        if when.utcoffset() is None:
            return "INVALID_STATUS"
        age=(now or datetime.now(timezone.utc))-when
        if age.total_seconds() > 48*3600:
            return "STALE" if outcome=="successful" else "FAILED_STALE"
        return "SUCCESSFUL" if outcome=="successful" else "FAILED"
    except (ValueError,OSError,TypeError,KeyError):
        return "INVALID_STATUS"


def main():
    if len(sys.argv)!=2:
        raise SystemExit("PROGRESS_754_STATUS=INVALID_ARGUMENTS")
    print("PROGRESS_754_STATUS="+report(sys.argv[1]))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
