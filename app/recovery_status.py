"""Point-in-time evidence that a Tracker backup passed an isolated restore.

A receipt is not proof that an archive remains valid forever. UI reads are
metadata-only; expensive ZIP extraction and hashing happen only in CLI jobs.
No database schema or live user data is modified.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from . import backup

RECEIPT_NAME = ".tracker-restore-receipt.json"
NAME_PATTERN = re.compile(r"tracker-[A-Za-z0-9-]+\.zip\Z")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def record_restore(archive: Path, stats: dict, backup_dir: Path | None = None) -> dict:
    """Record only after a successful full isolated restoration."""
    root = Path(backup_dir if backup_dir is not None else backup.BACKUP_DIR).resolve()
    path = Path(archive)
    if (not NAME_PATTERN.fullmatch(path.name)
            or path.is_symlink() or not path.is_file()
            or path.parent.resolve() != root):
        raise ValueError("Restore receipts require a regular configured backup archive")
    if not all(isinstance(stats.get(key), int) and stats[key] >= 0
               for key in ("files", "uploads", "tables", "bytes")):
        raise ValueError("Invalid isolated restoration result")
    if stats["files"] < 1 or stats["tables"] < 1:
        raise ValueError("Missing restored database content")
    before = path.stat()
    digest = _sha256(path)
    after = path.stat()
    if (before.st_mtime_ns, before.st_size, before.st_ino) != (
            after.st_mtime_ns, after.st_size, after.st_ino):
        raise ValueError("Backup changed during receipt recording")
    receipt = {
        "version": 1,
        "archive": path.name,
        "archive_bytes": after.st_size,
        "archive_mtime_ns": after.st_mtime_ns,
        "archive_sha256": digest,
        "verified_utc": datetime.now(timezone.utc).isoformat(),
        "files": stats["files"],
        "uploads": stats["uploads"],
        "tables": stats["tables"],
        "restored_bytes": stats["bytes"],
    }
    # Keep the receipt private and update atomically so the UI cannot read
    # a partially written success record.
    tmp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", prefix=".tracker-receipt-",
            suffix=".tmp", dir=root, delete=False
        ) as handle:
            tmp_name = handle.name
            os.fchmod(handle.fileno(), 0o600)
            json.dump(receipt, handle, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, root / RECEIPT_NAME)
    finally:
        if tmp_name is not None:
            Path(tmp_name).unlink(missing_ok=True)
    return receipt


def restore_status(backup_dir: Path | None = None, *, max_age_hours: float = 24,
                   now: datetime | None = None) -> dict:
    """Read one receipt without opening any ZIP or changing any files."""
    root = Path(backup_dir if backup_dir is not None else backup.BACKUP_DIR)
    receipt_path = root / RECEIPT_NAME
    result = {"ok": False, "state": "never", "archive": "",
              "verified_utc": "", "detail": "No isolated backup restore recorded"}
    try:
        if receipt_path.is_symlink() or not receipt_path.is_file():
            return result
        if receipt_path.stat().st_size > 8192:
            raise ValueError("Oversized recovery receipt")
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt.get("version") != 1:
            raise ValueError("Unsupported recovery receipt")
        name = receipt.get("archive", "")
        if not isinstance(name, str) or not NAME_PATTERN.fullmatch(name):
            raise ValueError("Invalid receipt archive name")
        verified = datetime.fromisoformat(receipt["verified_utc"])
        if verified.tzinfo is None:
            raise ValueError("Timezone missing from receipt")
        elapsed = ((now or datetime.now(timezone.utc)) -
                   verified.astimezone(timezone.utc)).total_seconds() / 3600
        result["archive"] = name
        result["verified_utc"] = verified.isoformat()
        if elapsed < 0 or elapsed > max_age_hours:
            result.update(state="old", detail="Last isolated restore result is outside the 24-hour freshness window")
            return result

        # A passing receipt must correspond to the newest current archive.
        # Comparing timestamps and size is metadata evidence, not a fresh hash.
        archives = backup.list_backups(root)
        if not archives or archives[0]["name"] != name:
            result.update(state="not_latest", detail="Latest backup has no recorded isolated restore")
            return result
        archive = root / name
        if archive.is_symlink() or not archive.is_file():
            raise ValueError("Verified backup archive missing or symlinked")
        info = archive.stat()
        if (type(receipt.get("archive_bytes")) is not int
                or type(receipt.get("archive_mtime_ns")) is not int
                or receipt["archive_bytes"] != info.st_size
                or receipt["archive_mtime_ns"] != info.st_mtime_ns):
            result.update(state="changed", detail="Backup archive changed since isolated restore")
            return result
        result.update(
            ok=True, state="verified",
            detail=f"Isolated restore passed for {name} ({elapsed:.1f} hours ago)",
        )
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        result.update(state="invalid", detail="Recovery receipt missing or invalid; rerun an isolated restore")
    return result
