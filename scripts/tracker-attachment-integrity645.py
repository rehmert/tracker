#!/usr/bin/env python3
"""Read-only, fast DB-to-upload integrity gate for Tracker releases."""
from __future__ import annotations
import argparse
import hashlib
import sqlite3
from pathlib import Path

TABLES = (("coas", "coa"), ("coa_attachments", "coa"), ("lab_reports", "labs"))

def inspect(data: Path, *, hashes: bool = False) -> int:
    db_file = data / "tracker.db"
    if not db_file.is_file():
        raise ValueError("Tracker SQLite database absent")
    with sqlite3.connect(f"file:{db_file}?mode=ro", uri=True) as db:
        db.execute("PRAGMA query_only=ON")
        checked = missing = invalid = mismatch = 0
        for table, folder in TABLES:
            if not db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone():
                continue
            columns = {item[1] for item in db.execute(f'PRAGMA table_info("{table}")')}
            if not {"id", "stored_name", "original_name"} <= columns:
                continue
            has_sha = hashes and "sha256" in columns
            query = f'SELECT id, stored_name, original_name, {"sha256" if has_sha else "NULL"} FROM "{table}"'
            for pk, stored, original, sha in db.execute(query):
                if not original:
                    continue
                checked += 1
                if (not stored or stored in (".", "..") or "/" in stored
                        or "\\" in stored or "\x00" in stored):
                    invalid += 1
                    print(f"INVALID_REFERENCE table={table} id={pk}")
                    continue
                fpath = data / "uploads" / folder / stored
                if fpath.is_symlink() or not fpath.is_file():
                    missing += 1
                    print(f"MISSING_REFERENCE table={table} id={pk} path=uploads/{folder}/{stored}")
                elif has_sha and sha:
                    digest = hashlib.file_digest(fpath.open("rb"), "sha256").hexdigest()
                    if digest.lower() != sha.lower():
                        mismatch += 1
                        print(f"HASH_MISMATCH table={table} id={pk} path=uploads/{folder}/{stored}")
    print(f"ATTACHMENT_REFERENCES_CHECKED={checked}")
    print(f"ATTACHMENT_FILES_MISSING={missing}")
    print(f"ATTACHMENT_REFERENCES_INVALID={invalid}")
    print(f"ATTACHMENT_HASH_MISMATCHES={mismatch}")
    status = "PASSED" if not (missing or invalid or mismatch) else "FAILED"
    print(f"ATTACHMENT_INTEGRITY={status}")
    return 0 if status == "PASSED" else 1

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--data", type=Path, required=True)
    p.add_argument("--hashes", action="store_true")
    a = p.parse_args()
    try:
        raise SystemExit(inspect(a.data.resolve(), hashes=a.hashes))
    except (OSError, ValueError, sqlite3.Error) as exc:
        raise SystemExit(f"ATTACHMENT_INTEGRITY=FAILED: {exc}")
