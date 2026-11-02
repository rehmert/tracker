"""Read-only capacity and filesystem placement signals for Tracker backups.

No archive contents are opened and no volume or database is mutated.
A capacity heuristic is not a guarantee that future backups will succeed.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from . import backup

MIB = 1024 * 1024
MIN_HEADROOM = 512 * MIB


def _size(number: int) -> str:
    if number >= 1024 * MIB:
        return f"{number / (1024 * MIB):,.1f} GiB"
    return f"{number / MIB:,.1f} MiB"


def backup_storage_status(
    primary_dir: Path | None = None,
    secondary_dir: Path | None = None,
) -> dict:
    """Summarize current disk headroom and secondary filesystem placement.

    Reports secondary copy placement separately from replica *integrity*.
    A separate filesystem can still be on the same host or physical device.
    """
    primary = Path(primary_dir if primary_dir is not None else backup.BACKUP_DIR)
    configured = os.getenv("TRACKER_BACKUP_REPLICA_DIR")
    secondary = Path(secondary_dir if secondary_dir is not None else
                     (configured or "/tracker-backups"))
    secondary_configured = bool(
        secondary_dir is not None or configured or secondary.exists()
    )
    result = {
        "primary": {
            "ok": False,
            "state": "unavailable",
            "detail": "Cannot inspect primary backup storage",
            "count": 0,
            "archive_bytes": 0,
        },
        "secondary": {
            "configured": secondary_configured,
            "ok": False,
            "state": "not_configured",
            "detail": "No secondary local directory configured",
        },
    }
    try:
        if primary.is_symlink() or not primary.is_dir():
            raise ValueError("Primary backup directory missing or symlinked")
        archives = backup.list_backups(primary)
        if any((primary / item["name"]).is_symlink() for item in archives):
            raise ValueError("Symlinked primary archive")
        disk = shutil.disk_usage(primary)
        latest = archives[0]["size"] if archives else 0
        total = sum(item["size"] for item in archives)
        # Approximation: compressed ZIP sizes cannot reliably predict the
        # temporary extraction footprint of SQLite and uploaded documents.
        headroom_target = max(MIN_HEADROOM, 3 * latest)
        adequate = disk.free >= headroom_target
        percent = 100 * disk.free / disk.total if disk.total else 0
        result["primary"] = {
            "ok": adequate,
            "state": "adequate" if adequate else "low",
            "free_bytes": disk.free,
            "total_bytes": disk.total,
            "archive_bytes": total,
            "count": len(archives),
            "headroom_bytes": headroom_target,
            "detail": (
                f"{_size(disk.free)} free ({percent:.0f}% of volume); "
                f"{len(archives)} backups totaling {_size(total)}; "
                f"advisory reserve {_size(headroom_target)}"
            ),
        }
    except (OSError, ValueError) as exc:
        result["primary"]["detail"] = f"Primary backup storage unavailable: {exc}"

    if not secondary_configured:
        return result
    try:
        if secondary.is_symlink() or not secondary.is_dir():
            raise ValueError("Secondary backup directory missing or symlinked")
        if primary.is_symlink() or not primary.is_dir():
            raise ValueError("Primary storage unavailable for comparison")
        if primary.resolve() == secondary.resolve():
            raise ValueError("Secondary directory is the primary directory")
        same_fs = primary.stat().st_dev == secondary.stat().st_dev
        secondary_disk = shutil.disk_usage(secondary)
        result["secondary"] = {
            "configured": True,
            "ok": not same_fs,
            "state": "same_filesystem" if same_fs else "different_filesystem",
            "detail": (
                f"{'Same' if same_fs else 'Different'} filesystem from primary; "
                f"{_size(secondary_disk.free)} free locally. "
                "Neither placement establishes an off-host backup."
            ),
        }
    except (OSError, ValueError) as exc:
        result["secondary"].update(
            configured=True, state="unavailable",
            detail=f"Cannot inspect secondary backup storage: {exc}",
        )
    return result
