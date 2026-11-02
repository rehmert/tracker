"""Lightweight read-only evidence for the secondary LOCAL backup copy.

A matching receipt is a point-in-time byte-comparison result, not an
off-host backup, continual checksum verification or full restore test.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
from datetime import datetime, timezone

from . import backup
from .recovery_status import NAME_PATTERN

RECEIPT = ".tracker-replica-receipt.json"
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def replica_health(source: Path | None = None, destination: Path | None = None,
                   *, max_age_hours: int = 24, now=None) -> dict:
    primary = Path(source if source is not None else backup.BACKUP_DIR)
    configured = os.getenv("TRACKER_BACKUP_REPLICA_DIR")
    replica = Path(destination if destination is not None else
                   (configured or "/tracker-backups"))
    result = {
        "configured": bool(configured or destination is not None or replica.exists()),
        "ok": False, "state": "not_configured",
        "detail": "Optional secondary local copy is not configured",
    }
    if not result["configured"]:
        return result
    try:
        if replica.is_symlink() or not replica.is_dir():
            raise ValueError("Secondary backup path is not a regular directory")
        if replica.resolve() == primary.resolve():
            raise ValueError("Secondary backup directory equals primary")
        receipt_path = replica / RECEIPT
        if receipt_path.is_symlink():
            raise ValueError("Symlinked secondary verification receipt")
        if not receipt_path.is_file():
            result.update(state="unverified",
                          detail="Secondary directory exists; no verified replication receipt")
            return result
        if receipt_path.stat().st_size > 8192:
            raise ValueError("Oversized secondary verification receipt")
        item = json.loads(receipt_path.read_text(encoding="utf-8"))
        name = item.get("latest_archive")
        stamp = item.get("verified_utc")
        if (item.get("version") != 1 or not isinstance(name, str)
                or not NAME_PATTERN.fullmatch(name)
                or not isinstance(item.get("latest_sha256"), str)
                or not SHA256.fullmatch(item["latest_sha256"])):
            raise ValueError("Invalid replica receipt fields")
        checked = datetime.fromisoformat(stamp)
        if checked.tzinfo is None:
            raise ValueError("Replica receipt lacks timezone")
        age = ((now or datetime.now(timezone.utc)) -
               checked.astimezone(timezone.utc)).total_seconds() / 3600
        if age < 0 or age > max_age_hours:
            result.update(state="stale",
                          detail="Secondary copy verification is older than 24 hours")
            return result
        if item.get("primary") != str(primary.resolve()) or item.get("secondary") != str(replica.resolve()):
            raise ValueError("Replica receipt belongs to a different directory")
        archives = backup.list_backups(primary)
        if not archives or archives[0]["name"] != name:
            result.update(state="behind", detail="Secondary copy not verified for the newest primary backup")
            return result
        src, dst = primary / name, replica / name
        if (src.is_symlink() or dst.is_symlink()
                or not src.is_file() or not dst.is_file()):
            raise ValueError("Newest backup copy is missing or symlinked")
        a, b = src.stat(), dst.stat()
        for key, actual in (
            ("primary_bytes", a.st_size), ("primary_mtime_ns", a.st_mtime_ns),
            ("secondary_bytes", b.st_size), ("secondary_mtime_ns", b.st_mtime_ns),
        ):
            if type(item.get(key)) is not int or item[key] != actual:
                result.update(state="changed", detail="Backup changed since last secondary copy verification")
                return result
        result.update(
            ok=True, state="verified",
            detail=f"Local secondary copy byte-matched: {name} ({age:.1f} h ago); not off-host",
        )
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        result.update(state="invalid",
                      detail="Cannot validate local secondary backup verification; rerun replication")
    return result
