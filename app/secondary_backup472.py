"""Release 472: local administrator-operated private snapshot.

No HTTP endpoint, database mutation, user login activation,
or browser-selected backup path.
"""
import json
import os
import sqlite3
import sys
import uuid
from contextlib import closing
from pathlib import Path

from .worker_scope428 import worker_plan428


def backup_secondary472(user_id):
    paths = worker_plan428(user_id)
    backup_dir = paths.backups

    if (
        backup_dir.is_symlink()
        or not backup_dir.is_dir()
        or backup_dir != paths.root / "backups"
    ):
        raise RuntimeError("Private backup directory unavailable")

    name = "tracker-private-" + uuid.uuid4().hex + ".sqlite3"
    destination = backup_dir / name

    fd = os.open(
        destination,
        os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW,
        0o600,
    )
    os.close(fd)
    completed = False

    try:
        with closing(sqlite3.connect(
            "file:" + str(paths.database) + "?mode=ro",
            uri=True,
        )) as source:
            marker = source.execute("""
                SELECT user_id,status,schema_version
                FROM tracker_staged_workspace426
            """).fetchall()
            if marker != [(user_id, "inactive", 426)]:
                raise RuntimeError("Workspace identity mismatch")

            with closing(sqlite3.connect(destination)) as target:
                source.backup(target)

        with closing(sqlite3.connect(
            "file:" + str(destination) + "?mode=ro",
            uri=True,
        )) as checked:
            if checked.execute(
                "PRAGMA quick_check"
            ).fetchall() != [("ok",)]:
                raise RuntimeError("Backup integrity failed")
            if checked.execute("""
                SELECT user_id,status,schema_version
                FROM tracker_staged_workspace426
            """).fetchall() != [(user_id, "inactive", 426)]:
                raise RuntimeError("Backup identity mismatch")

        completed = True
        return {
            "user_id": user_id,
            "filename": name,
            "bytes": destination.stat().st_size,
            "status": "verified",
        }
    finally:
        if not completed:
            destination.unlink(missing_ok=True)


def main():
    from . import config

    if config.instance_label() != "DEV":
        raise PermissionError("DEV only")
    if len(sys.argv) != 2 or not sys.argv[1].isdecimal():
        raise ValueError("Usage: python -m app.secondary_backup472 USER_ID")
    uid = int(sys.argv[1])
    if uid <= 1:
        raise PermissionError("Administrator database not supported")
    print(json.dumps(backup_secondary472(uid), sort_keys=True))


if __name__ == "__main__":
    main()
