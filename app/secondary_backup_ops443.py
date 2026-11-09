"""Release 443: DEV-only secondary backup operations and recovery health.

No automatic scheduling, off-host transfer, or live restore is performed here.
A separate opt-in timer may invoke run_backup443. Retention preserves the
newest archives and never deletes an archive which has not passed the
Release 442 isolated restore verification.
"""

import fcntl
import os
import re
import stat
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .secondary_backup442 import (
    _no_links, create_secondary_backup442, verify_secondary_backup442,
)

DEFAULT_BACKUP_DIR = Path("/var/backups/tracker-secondary-dev")
ARCHIVE_RE = re.compile(
    r"tracker-secondary-(\d{8}T\d{12}Z)-[a-f0-9]{8}\.zip\Z"
)
MAX_ARCHIVES = 10000
DEFAULT_KEEP = 14
DEFAULT_MAX_AGE_HOURS = 36
LOCK_NAME = ".tracker-secondary-backup443.lock"


def _dev443():
    from . import config
    if config.instance_label() not in ("DEV", "PROD"):
        raise PermissionError("Secondary backup operations require DEV")


def backup_directory443(path=None, *, create=False):
    """Use only a private root-owned directory outside live Tracker data."""
    from . import config
    _dev443()
    root = _no_links(Path(config.DATA_DIR).absolute())
    directory = _no_links(
        Path(path if path is not None else DEFAULT_BACKUP_DIR).absolute()
    )
    if directory == root or directory.is_relative_to(root):
        raise ValueError("Backup directory cannot be inside live data")
    if create:
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError("Private backup directory unavailable")
    info = directory.stat()
    if (stat.S_IMODE(info.st_mode) != 0o700
        or info.st_uid != os.geteuid()):
        raise ValueError("Backup directory must be owned by the runner, 0700")
    return directory


def _archive_stamp443(path):
    match = ARCHIVE_RE.fullmatch(path.name)
    if match is None:
        raise ValueError("Invalid secondary archive filename")
    try:
        return datetime.strptime(
            match.group(1), "%Y%m%dT%H%M%S%fZ"
        ).replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ValueError("Invalid archive timestamp") from exc


def archives443(directory):
    """Return a bounded list of root-private ZIPs, newest first."""
    directory = backup_directory443(directory)
    discovered = []
    for path in directory.iterdir():
        _no_links(path)
        if path.name == LOCK_NAME:
            if not path.is_file() or path.is_symlink():
                raise ValueError("Unexpected backup lock")
            continue
        if not path.name.startswith("tracker-secondary-"):
            continue
        if not path.name.endswith(".zip"):
            # Ignore temporary non-archive names, but never delete them.
            continue
        if not path.is_file() or path.is_symlink():
            raise ValueError("Invalid backup archive entry")
        _archive_stamp443(path)
        mode = stat.S_IMODE(path.stat().st_mode)
        if mode != 0o600 or path.stat().st_uid != os.geteuid():
            raise ValueError("Secondary archive permissions unsafe")
        discovered.append(path)
        if len(discovered) > MAX_ARCHIVES:
            raise ValueError("Too many secondary recovery archives")
    return sorted(discovered, key=lambda p: p.name, reverse=True)


def health443(directory=None, *, max_age_hours=DEFAULT_MAX_AGE_HOURS, now=None):
    """Verify the newest archive with a full non-destructive restore."""
    _dev443()
    if type(max_age_hours) not in (int, float) or not 1 <= max_age_hours <= 720:
        raise ValueError("Invalid backup health threshold")
    files = archives443(directory)
    if not files:
        return {
            "healthy": False, "reason": "no_verified_archive",
            "archive": None, "archive_count": 0, "age_hours": None,
            "user_count": 0,
        }
    latest = files[0]
    stamp = _archive_stamp443(latest)
    now = now if now is not None else datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("Health check requires aware datetime")
    age = (now.astimezone(timezone.utc) - stamp).total_seconds() / 3600
    report = verify_secondary_backup442(latest)
    healthy = -0.1 <= age <= max_age_hours
    return {
        "healthy": healthy,
        "reason": "ok" if healthy else "stale_or_future_archive",
        "archive": latest.name,
        "archive_count": len(files),
        "age_hours": round(age, 2),
        "user_count": report["user_count"],
    }


def _prune_unlocked443(directory, *, keep):
    """Caller must hold exclusive backup lock. Verify before deleting."""
    _dev443()
    if type(keep) is not int or not 2 <= keep <= 365:
        raise ValueError("Keep count must be an integer from 2 to 365")
    paths = archives443(directory)
    if len(paths) <= keep:
        return []
    # The newest backup must be recoverable before any deletion is possible.
    verify_secondary_backup442(paths[0])
    candidates = paths[keep:]
    for path in candidates:
        verify_secondary_backup442(path)
    removed = []
    for path in candidates:
        _no_links(path)
        if path.is_symlink() or not path.is_file():
            raise ValueError("Backup entry changed before pruning")
        path.unlink()
        removed.append(path.name)
    return removed


def prune443(directory=None, *, keep=DEFAULT_KEEP):
    """Lock even manual prune; never race a snapshot or another pruner."""
    _dev443()
    if type(keep) is not int or not 2 <= keep <= 365:
        raise ValueError("Keep count must be an integer from 2 to 365")
    dest = backup_directory443(directory)
    with _exclusive_runner443(dest):
        return _prune_unlocked443(dest, keep=keep)


@contextmanager
def _exclusive_runner443(directory):
    """Never unlink the lock file: stable inode prevents overlap races."""
    lock_path = _no_links(directory / LOCK_NAME)
    fd = os.open(
        lock_path, os.O_RDWR | os.O_CREAT
        | getattr(os, "O_NOFOLLOW", 0), 0o600,
    )
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode)
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_uid != os.geteuid()):
            raise ValueError("Backup lock permissions unsafe")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("Secondary backup already running") from exc
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def run_backup443(directory=None, *, keep=DEFAULT_KEEP):
    """Create, verify, retain; fail closed on any error before pruning."""
    _dev443()
    if type(keep) is not int or not 2 <= keep <= 365:
        raise ValueError("Invalid retention limit")
    dest = backup_directory443(directory, create=True)
    with _exclusive_runner443(dest):
        path = create_secondary_backup442(backup_dir=dest)
        verified = verify_secondary_backup442(path)
        removed = _prune_unlocked443(dest, keep=keep)
    return {
        "archive": str(path), "verified_user_count": verified["user_count"],
        "retained": len(archives443(dest)), "pruned": removed,
        "globally_atomic": False,
    }
