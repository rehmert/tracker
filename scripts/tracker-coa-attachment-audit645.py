#!/usr/bin/env python3
"""Read-only Release 645 DEV diagnostic for unresolved attachment references.

Does not modify the database, uploads, backups, or deployed code.
"""
from __future__ import annotations

import os
import re
import sqlite3
import zipfile
from collections import defaultdict
from pathlib import Path


def configured_data_dir() -> Path:
    env = Path("/etc/tracker.env")
    values = {}
    for line in env.read_text().splitlines():
        match = re.match(r'^\\s*(?:export\\s+)?(TRACKER_INSTANCE|TRACKER_DATA_DIR)\\s*=(.*)$', line)
        if match:
            values[match.group(1)] = match.group(2).strip().strip("\\\"'")
    if values.get("TRACKER_INSTANCE", "").upper() != "DEV":
        raise SystemExit("AUDIT_DENIED: This diagnostic is DEV-only")
    raw = values.get("TRACKER_DATA_DIR", "/opt/tracker/data")
    data = Path(raw)
    if not data.is_absolute():
        data = Path("/opt/tracker/data")
    return data.resolve()


def read_references(db_file: Path):
    # Read-only SQLite URI. Do not open a connection that can write to data.
    db = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
    try:
        db.execute("PRAGMA query_only=ON")
        for table, folder in (("coas", "coa"), ("coa_attachments", "coa"), ("lab_reports", "labs")):
            exists = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            if not exists:
                continue
            cols = {col[1] for col in db.execute(f'PRAGMA table_info("{table}")')}
            if not {"id", "stored_name", "original_name"} <= cols:
                continue
            for ident, stored, original in db.execute(
                f'SELECT id, stored_name, original_name FROM "{table}"'
            ):
                if not original:
                    continue
                if not stored or stored in (".", "..") or "/" in stored or "\\\\" in stored:
                    yield (table, ident, f"INVALID_STORED_NAME:{stored!r}", original)
                else:
                    yield (table, ident, f"uploads/{folder}/{stored}", original)
    finally:
        db.close()


def main():
    data = configured_data_dir()
    db_file = data / "tracker.db"
    if not db_file.is_file():
        raise SystemExit("AUDIT_DENIED: Configured DEV database not found")
    refs = list(read_references(db_file))
    missing = [(table, ident, rel, original) for table, ident, rel, original in refs
               if rel.startswith("INVALID_") or not (data / rel).is_file()]
    print(f"COA_645_ATTACHMENT_REFERENCES={len(refs)}")
    print(f"COA_645_MISSING_REFERENCES={len(missing)}")
    print(f"COA_645_DATA_DIRECTORY={data}")
    if not missing:
        print("COA_645_ATTACHMENT_AUDIT=COMPLETE")
        print("LIVE_DB=UNMODIFIED")
        return

    # Examine archive entry inventories only. Never extract or restore files.
    backup_root = Path(os.getenv("TRACKER_BACKUP_DIR", str(data.parent / "backups"))).resolve()
    missing_paths = {rel for _, _, rel, _ in missing if rel.startswith("uploads/")}
    archive_hits = defaultdict(list)
    archive_count = 0
    if backup_root.is_dir():
        for archive in sorted(backup_root.glob("tracker-*.zip"), reverse=True):
            if archive.is_symlink() or not archive.is_file():
                continue
            archive_count += 1
            try:
                with zipfile.ZipFile(archive) as z:
                    entries = set(z.namelist())
                for rel in (missing_paths & entries):
                    archive_hits[rel].append(archive.name)
            except (OSError, zipfile.BadZipFile) as exc:
                print(f"ARCHIVE_UNREADABLE={archive.name}: {type(exc).__name__}")
    print(f"COA_645_ARCHIVES_INDEXED={archive_count}")
    for table, ident, rel, original in missing:
        hits = archive_hits[rel]
        print(f"MISSING table={table} id={ident} stored={rel} original={original!r} "
              f"candidate_archives={len(hits)}"
              + (f" newest_archive={hits[0]}" if hits else ""))
    print("ARCHIVE_MATCHES_ARE_NOT_VERIFIED_RESTORES")
    print("REPAIR=NONE; DELETE=NONE; BACKUP_GUARD=UNCHANGED")
    print("LIVE_DB=UNMODIFIED")


if __name__ == "__main__":
    main()
