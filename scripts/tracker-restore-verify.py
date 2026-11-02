#!/usr/bin/env python3
"""Non-destructive dry-run of an existing Tracker SQLite-and-uploads archive."""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path, PurePosixPath
import sqlite3
import stat
import tempfile
import zipfile


def validate_member(name: str) -> Path:
    parts = name.split("/")
    pure = PurePosixPath(name)
    if (not name or name.startswith("/") or "\\" in name or ":" in name
            or pure.is_absolute() or any(p in ("", ".", "..") for p in parts)
            or (name != "tracker.db"
                and not (len(pure.parts) >= 3 and pure.parts[0] == "uploads"))):
        raise ValueError(f"Unsafe archive member: {name[:100]}")
    return Path(*pure.parts)


def restore_check(archive: Path, max_bytes: int = 10 * 1024**3) -> dict:
    if archive.is_symlink() or not archive.is_file():
        raise ValueError("Archive missing or symlinked")
    if max_bytes < 1:
        raise ValueError("Invalid restore limit")
    # Check paths, duplicate names, symlinks and sizes before streaming checksums.
    with zipfile.ZipFile(archive) as z:
        members = z.infolist()
        if len(members) != len({m.filename for m in members}):
            raise ValueError("Duplicate archive entries")
        if sum(m.file_size for m in members) > max_bytes + 1048576:
            raise ValueError("Archive exceeds restore limit")
        for info in members:
            if info.filename != "manifest.json":
                validate_member(info.filename)
            if stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK:
                raise ValueError("Archive contains a symlink")

    from app.backup import verify_backup
    manifest = verify_backup(archive)
    files = manifest["files"]
    if sum(int(v["bytes"]) for v in files.values()) > max_bytes:
        raise ValueError("Archive exceeds restore limit")

    # No path in the live Tracker data tree is ever opened for writing.
    with tempfile.TemporaryDirectory(prefix="tracker-restore-check-") as directory:
        root = Path(directory)
        total = 0
        with zipfile.ZipFile(archive) as z:
            for name, expected in files.items():
                relative = validate_member(name)
                info = z.getinfo(name)
                if total + info.file_size > max_bytes:
                    raise ValueError("Restore size limit exceeded")
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                size = 0
                with z.open(info) as source, path.open("xb") as dest:
                    while True:
                        chunk = source.read(1024 * 1024)
                        if not chunk:
                            break
                        size += len(chunk)
                        total += len(chunk)
                        if total > max_bytes:
                            raise ValueError("Restore size limit exceeded")
                        digest.update(chunk)
                        dest.write(chunk)
                if (size != expected["bytes"]
                        or digest.hexdigest() != expected["sha256"]):
                    raise ValueError(f"Restored content mismatch: {name}")

        db = root / "tracker.db"
        with sqlite3.connect(db.as_uri() + "?mode=ro", uri=True) as connection:
            if connection.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Restored SQLite integrity failed")
            if connection.execute("PRAGMA foreign_key_check").fetchmany(10):
                raise ValueError("Restored SQLite foreign keys failed")
            tables = connection.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
            ).fetchone()[0]
            if tables < 1:
                raise ValueError("Restored database contains no tables")
    return {"files": len(files), "bytes": total, "tables": tables,
            "uploads": sum(p.startswith("uploads/") for p in files)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--max-bytes", type=int, default=10 * 1024**3)
    parser.add_argument("--record-status", action="store_true",
                        help="Store restore evidence for a configured Tracker archive")
    args = parser.parse_args()
    try:
        before = args.archive.stat()
        stats = restore_check(args.archive, args.max_bytes)
        after = args.archive.stat()
        if (before.st_size, before.st_mtime_ns, before.st_ino) != (
                after.st_size, after.st_mtime_ns, after.st_ino):
            raise ValueError("Archive changed during isolated restore")
        if args.record_status:
            from app.recovery_status import record_restore
            record_restore(args.archive, stats)
            print("PASS: Recovery receipt recorded for configured backup")
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error,
            zipfile.BadZipFile) as exc:
        print(f"FAIL: Isolated restore: {type(exc).__name__}: {str(exc)[:180]}")
        return 1
    print("PASS: Isolated restore completed; live data untouched")
    print(f"Files: {stats['files']}; uploads: {stats['uploads']}; "
          f"bytes: {stats['bytes']}; tables: {stats['tables']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
