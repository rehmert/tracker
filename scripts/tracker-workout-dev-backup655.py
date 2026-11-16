#!/usr/bin/env python3
"""Release 655 DEV-only verified workout migration archive, preserving exactly two known missing references.

Never use in PROD. The archive contains the exact SQLite snapshot plus every
present upload. The known missing DEV-only files remain missing references;
no rows or binary files are fabricated. This is NOT a fully complete COA backup.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import tempfile
import zipfile
from contextlib import closing, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

from app.backup_consistency309 import upload_inventory
from app.backup_references341 import required_attachments
from app.upload_coordination325 import upload_guard
# The established Release 650 gate is an executable with hyphens in its
# filename, not an importable Python module. Load that exact adjacent file
# by path; do not rename it or maintain a divergent copy of its DEV policy.
import runpy

_gate650 = runpy.run_path(
    str(Path(__file__).resolve().parent / "tracker-dev-attachment-gate650.py")
)
verify_dev_instance = _gate650["verify_dev_instance"]
attachment_gate = _gate650["main"]

ALLOWED_MISSING = frozenset({
    "uploads/coa/b94356f52d964400b481e6c743484367.png",
    "uploads/coa/35ddd15d235246258cd8ed0b69fef3c6.png",
})


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1048576), b""):
            h.update(chunk)
    return h.hexdigest()


def assert_sqlite(path):
    with closing(sqlite3.connect(path)) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("SQLite integrity verification failed")
        if db.execute("PRAGMA foreign_key_check").fetchmany(1):
            raise ValueError("SQLite foreign key verification failed")


def files_present(data):
    uploads = data / "uploads"
    if not uploads.is_dir() or uploads.is_symlink():
        raise ValueError("DEV uploads directory must be a real directory")
    found = {}
    for path in sorted(uploads.rglob("*")):
        if path.is_symlink():
            raise ValueError("Upload symlink encountered")
        if path.is_file():
            rel = path.relative_to(data).as_posix()
            if not rel.startswith("uploads/") or ".." in Path(rel).parts:
                raise ValueError("Unsafe DEV upload path")
            found[rel] = path
    return found


def verify_archive(archive, known_missing):
    with tempfile.TemporaryDirectory(prefix="tracker-dev655-restore-") as temp:
        root = Path(temp)
        with zipfile.ZipFile(archive) as zipf:
            names = zipf.namelist()
            if len(names) != len(set(names)):
                raise ValueError("Repeated archive member")
            manifest = json.loads(zipf.read("manifest.json"))
            if manifest.get("kind") != "DEV-655-INCOMPLETE-ATTACHMENT-REVIEW":
                raise ValueError("Unexpected archive kind")
            records = manifest.get("files")
            if not isinstance(records, dict) or set(names) != set(records) | {"manifest.json"}:
                raise ValueError("Archive manifest mismatch")
            if manifest.get("known_missing") != known_missing:
                raise ValueError("Missing-reference evidence mismatch")
            for name, record in records.items():
                rel = Path(name)
                if (rel.is_absolute() or ".." in rel.parts or
                        name != "tracker.db" and not name.startswith("uploads/")):
                    raise ValueError("Unsafe archive member")
                raw = zipf.read(name)
                if (len(raw) != record["bytes"] or
                        hashlib.sha256(raw).hexdigest() != record["sha256"]):
                    raise ValueError("Archive checksum mismatch")
                path = root / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
        assert_sqlite(root / "tracker.db")
        current = required_attachments(root / "tracker.db") - set(records)
        if sorted(current) != known_missing:
            raise ValueError("Restored database attachment references changed")
        return len(records)



def verify_dev_attachment_gate(data):
    """Send diagnostics to stderr; stdout is exclusively the archive pathname.

    The shell runner assigns ARCHIVE from stdout via command substitution.
    Any diagnostic on stdout corrupts that pathname and breaks deployment.
    """
    with redirect_stdout(os.sys.stderr):
        result = attachment_gate(["--data", str(data)])
    if result != 0:
        raise ValueError("DEV present attachment hashes or paths failed integrity")



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--dest", type=Path, required=True)
    args = parser.parse_args()
    verify_dev_instance()
    if os.geteuid() != 0 or os.uname().nodename.split(".")[0] != "tracker-dev":
        raise ValueError("Root on tracker-dev required")
    data = args.data.resolve()
    dest = args.dest.resolve()
    if not data.joinpath("tracker.db").is_file() or dest.is_symlink():
        raise ValueError("Invalid DEV database or backup destination")
    verify_dev_attachment_gate(data)
    dest.mkdir(mode=0o700, parents=True, exist_ok=True)
    with upload_guard(data):
        inventory_before = upload_inventory(data / "uploads")
        with tempfile.TemporaryDirectory(prefix=".dev655-", dir=dest) as temp:
            snapshot = Path(temp) / "tracker.db"
            with closing(sqlite3.connect("file:" + str(data / "tracker.db") + "?mode=ro", uri=True)) as src:
                with closing(sqlite3.connect(snapshot)) as dst:
                    src.backup(dst)
            assert_sqlite(snapshot)
            present = files_present(data)
            missing = sorted(required_attachments(snapshot) - set(present))
            if not set(missing).issubset(ALLOWED_MISSING):
                raise ValueError("Unexpected missing DEV attachments: " + repr(missing[:3]))
            sources = {"tracker.db": snapshot, **present}
            manifest = {
                "kind": "DEV-655-INCOMPLETE-ATTACHMENT-REVIEW",
                "known_missing": missing,
                "files": {name: {"bytes": path.stat().st_size, "sha256": digest(path)}
                          for name, path in sources.items()},
            }
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            archive = dest / ("tracker-dev655-" + stamp + ".zip")
            staged = Path(temp) / "candidate.zip"
            with zipfile.ZipFile(staged, "w", compression=zipfile.ZIP_DEFLATED) as z:
                for name, path in sources.items():
                    z.write(path, name)
                z.writestr("manifest.json", json.dumps(manifest, sort_keys=True))
            if upload_inventory(data / "uploads") != inventory_before:
                raise ValueError("DEV uploads changed while backing up")
            restored_count = verify_archive(staged, missing)
            if restored_count != len(sources):
                raise ValueError("Archive restore count mismatch")
            os.replace(staged, archive)
            archive.chmod(0o600)
    print("DEV_655_MISSING_REFERENCE_EXCEPTIONS=" + str(len(missing)), file=os.sys.stderr)
    print("DEV_655_DATABASE_AND_PRESENT_UPLOADS_RESTORED=PASSED", file=os.sys.stderr)
    print(archive)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
