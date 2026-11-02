#!/usr/bin/env python3
"""Verify and atomically mirror Tracker archives to a secondary local directory.

Only regular tracker-*.zip files are managed. Never modify the primary.
Every existing destination must match its primary SHA-256, and every new
copy must pass ZIP/SQLite validation before it replaces a destination name.
Retention runs only after all selected archives have been verified.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone

# Compatible with direct execution from a cron/systemd job without PYTHONPATH.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.backup import verify_backup

NAME = re.compile(r"tracker-[A-Za-z0-9-]+\.zip\Z")
RECEIPT = ".tracker-replica-receipt.json"


def fingerprint(path: Path) -> str:
    hash_ = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hash_.update(block)
    return hash_.hexdigest()


def identity(path: Path):
    stat = path.stat()
    return stat.st_dev, stat.st_ino, stat.st_mtime_ns, stat.st_size


def regular(path: Path) -> bool:
    return not path.is_symlink() and path.is_file()


def _atomic_receipt(destination: Path, info: dict) -> None:
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=destination,
            prefix=".tracker-replica-", suffix=".tmp", delete=False
        ) as stream:
            temp_path = Path(stream.name)
            os.fchmod(stream.fileno(), 0o600)
            json.dump(info, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        dest = destination / RECEIPT
        if dest.is_symlink():
            raise ValueError("Replica receipt must not be a symlink")
        os.replace(temp_path, dest)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _copy_verified(source: Path, target: Path, expected: str, before) -> None:
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(
            "wb", prefix=".tracker-copy-", suffix=".tmp",
            dir=target.parent, delete=False
        ) as destination:
            tmp = Path(destination.name)
            os.fchmod(destination.fileno(), 0o600)
            with source.open("rb") as original:
                shutil.copyfileobj(original, destination, length=1024 * 1024)
            destination.flush()
            os.fsync(destination.fileno())

        if identity(source) != before or fingerprint(tmp) != expected:
            raise ValueError(f"Primary changed during replica copy: {source.name}")
        if target.exists() or target.is_symlink():
            raise FileExistsError(f"Replica appeared during copy: {target.name}")
        os.replace(tmp, target)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


def replicate(primary: Path, secondary: Path, keep: int = 90) -> dict:
    primary, secondary = Path(primary), Path(secondary)
    if keep < 1:
        raise ValueError("Retention must be at least one")
    if (primary.is_symlink() or secondary.is_symlink()
            or not primary.is_dir() or not secondary.is_dir()):
        raise ValueError("Both source and destination must be existing, regular directories")
    primary = primary.resolve()
    secondary = secondary.resolve()
    if primary == secondary or primary in secondary.parents or secondary in primary.parents:
        raise ValueError("Source and destination must not contain one another")
    archives = sorted(primary.glob("tracker-*.zip"), key=lambda p: p.name, reverse=True)
    if not archives:
        raise ValueError("No primary Tracker archives; refusal to prune secondary")
    if any(not NAME.fullmatch(p.name) or not regular(p) for p in archives):
        raise ValueError("Unsafe or nonregular primary archive")
    selected = archives[:keep]

    # Validate newest snapshot every run; validate each new copy before
    # publishing. Existing copies are checked against source hashes.
    verify_backup(selected[0])
    copied = 0
    matched = 0
    latest_digest = ""
    latest_stat = None
    latest_replica_stat = None

    for archive in selected:
        before = identity(archive)
        digest = fingerprint(archive)
        if identity(archive) != before:
            raise ValueError(f"Primary archive changed during hashing: {archive.name}")
        target = secondary / archive.name
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise ValueError(f"Unsafe replica file: {target.name}")
        if target.exists():
            if fingerprint(target) != digest:
                raise ValueError(f"Existing replica hash mismatch: {target.name}")
            matched += 1
        else:
            if archive != selected[0]:
                verify_backup(archive)
            _copy_verified(archive, target, digest, before)
            copied += 1
        if identity(archive) != before:
            raise ValueError(f"Primary changed during replication: {archive.name}")
        if archive == selected[0]:
            latest_digest = digest
            latest_stat = archive.stat()
            latest_replica_stat = target.stat()

    # Refuse unknown/symlinked candidate names rather than deleting them.
    old = sorted(secondary.glob("tracker-*.zip"), key=lambda p: p.name, reverse=True)
    if any(not NAME.fullmatch(p.name) or not regular(p) for p in old):
        raise ValueError("Unsafe replica in retention set")
    removed = 0
    for entry in old[keep:]:
        entry.unlink()
        removed += 1

    info = {
        "version": 1,
        "verified_utc": datetime.now(timezone.utc).isoformat(),
        "primary": str(primary),
        "secondary": str(secondary),
        "latest_archive": selected[0].name,
        "latest_sha256": latest_digest,
        "primary_bytes": latest_stat.st_size,
        "primary_mtime_ns": latest_stat.st_mtime_ns,
        "secondary_bytes": latest_replica_stat.st_size,
        "secondary_mtime_ns": latest_replica_stat.st_mtime_ns,
        "selected_archives": len(selected),
        "copied": copied,
        "matched": matched,
        "pruned": removed,
    }
    _atomic_receipt(secondary, info)
    return info


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(
        os.getenv("TRACKER_BACKUP_DIR", "/opt/tracker/backups")))
    parser.add_argument("--dest", type=Path, default=Path(
        os.getenv("TRACKER_BACKUP_REPLICA_DIR", "/tracker-backups")))
    parser.add_argument("--keep", type=int, default=90)
    args = parser.parse_args()
    try:
        result = replicate(args.source, args.dest, args.keep)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(f"FAIL: Local replica verification: {error}", file=sys.stderr)
        return 1
    print("PASS: Secondary local copy verified against primary archives")
    print(f"Latest: {result['latest_archive']}; SHA-256: {result['latest_sha256']}")
    print(f"Copied: {result['copied']}; matched: {result['matched']}; "
          f"pruned: {result['pruned']}; local directory: {result['secondary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
