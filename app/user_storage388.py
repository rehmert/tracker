"""Release 388: fail-closed, inactive per-user storage foundation.

No live request or SQLAlchemy engine is routed through this
module yet. User 1 retains the original legacy data paths.
Other account IDs are not authorized to access any live data.

Future per-user databases must receive their schema through
a separately reviewed migration. Merely provisioning a
directory does not enable an account or database.
"""

from dataclasses import dataclass
from pathlib import Path
import os
import sqlite3
import stat

from . import config


@dataclass(frozen=True)
class StoragePaths:
    user_id: int
    mode: str
    root: Path
    database: Path
    coa: Path
    labs: Path
    backups: Path


def valid_user_id(user_id):
    if type(user_id) is not int:
        raise ValueError("User ID must be an integer")

    if not 1 <= user_id <= 2147483647:
        raise ValueError("Invalid user ID")

    return user_id


def _no_links(root, destination):
    """Reject symlinks at and below the trusted data root."""
    root = Path(root).absolute()
    destination = Path(destination).absolute()

    if not destination.is_relative_to(root):
        raise ValueError("Storage path escapes data root")

    current = root
    if current.is_symlink():
        raise ValueError("Data root is a symlink")

    for part in destination.relative_to(root).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("Symlinked user storage is forbidden")

    return destination


def planned_storage(user_id, data_root=None):
    """Return a plan; no mkdir, database creation or migration."""
    uid = valid_user_id(user_id)

    root = Path(
        data_root if data_root is not None else config.DATA_DIR
    ).absolute()

    if uid == 1:
        return StoragePaths(
            user_id=1,
            mode="legacy-admin",
            root=root,
            database=root / "tracker.db",
            coa=root / "uploads" / "coa",
            labs=root / "uploads" / "labs",
            # Legacy backups remain controlled by app.backup.
            backups=root / "backups",
        )

    private = root / "users" / str(uid)

    paths = StoragePaths(
        user_id=uid,
        mode="reserved-inactive",
        root=private,
        database=private / "tracker.db",
        coa=private / "uploads" / "coa",
        labs=private / "uploads" / "labs",
        backups=private / "backups",
    )

    for value in (
        paths.root,
        paths.database,
        paths.coa,
        paths.labs,
        paths.backups,
    ):
        _no_links(root, value)

    return paths


def live_storage_for(user_id):
    """Only the original administrator can access live data.

    This function is intentionally not wired into app.db.
    """
    uid = valid_user_id(user_id)

    if uid != 1:
        raise PermissionError(
            "Additional users are disabled until isolation rollout"
        )

    paths = planned_storage(uid)

    if paths.database.is_symlink() or not paths.database.is_file():
        raise RuntimeError("Legacy administrator database unavailable")

    return paths


def prepare_inactive_storage(user_id, data_root):
    """Provision EMPTY future-user paths only; never activate them.

    Not used by application routes. Intended for isolation
    tests and later admin-controlled provisioning.
    """
    uid = valid_user_id(user_id)

    if uid == 1:
        raise PermissionError(
            "Legacy administrator storage must never be reprovisioned"
        )

    root = Path(data_root).absolute()
    paths = planned_storage(uid, root)

    if not root.is_dir() or root.is_symlink():
        raise ValueError("Trusted data root required")

    # Exclusive first-time provisioning. Refuse existing
    # directories, including partially provisioned stores.
    users_root = root / "users"
    _no_links(root, users_root)

    if users_root.exists():
        if not users_root.is_dir():
            raise ValueError("Invalid users directory")
    else:
        users_root.mkdir(mode=0o700)

    os.chmod(users_root, 0o700)

    if paths.root.exists() or paths.root.is_symlink():
        raise FileExistsError(
            "User storage already exists; refusing overwrite"
        )

    paths.root.mkdir(mode=0o700)

    for folder in (
        paths.root / "uploads",
        paths.coa,
        paths.labs,
        paths.backups,
    ):
        folder.mkdir(mode=0o700)
        os.chmod(folder, 0o700)

    descriptor = os.open(
        paths.database,
        os.O_RDWR | os.O_CREAT | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    os.close(descriptor)

    # Initialize only an empty, valid SQLite file.
    # No Tracker tables, users, or personal records.
    with sqlite3.connect(paths.database) as db:
        db.execute("PRAGMA application_id=0")

    os.chmod(paths.database, 0o600)

    return paths


def inspect_storage(user_id, data_root=None):
    """Read-only overview without personal record contents."""
    paths = planned_storage(user_id, data_root)

    return {
        "user_id": paths.user_id,
        "mode": paths.mode,
        "database_exists": (
            paths.database.is_file()
            and not paths.database.is_symlink()
        ),
        "coa_directory_exists": paths.coa.is_dir(),
        "lab_directory_exists": paths.labs.is_dir(),
        "live_access_allowed": paths.user_id == 1,
    }
