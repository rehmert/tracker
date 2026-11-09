#!/usr/bin/env python3
"""Recover the administrator on explicitly enabled DEV or PROD sessions."""

import getpass
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


def main():
    if os.geteuid() != 0:
        raise RuntimeError("Root privileges required")

    # Use the configured live instance and data path.
    import shlex

    settings = {}
    for line in Path("/etc/tracker.env").read_text().splitlines():
        line = line.strip()
        if line.startswith("export "):
            line = line[7:].strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw = line.split("=", 1)
        if key in ("TRACKER_INSTANCE", "TRACKER_DATA_DIR"):
            values = shlex.split(raw, comments=False)
            if len(values) != 1:
                raise RuntimeError(f"Invalid {key}")
            settings[key] = values[0]

    instance = settings.get("TRACKER_INSTANCE", "").upper()
    if instance not in ("DEV", "PROD"):
        raise RuntimeError("Explicit DEV or PROD identity required")

    os.environ["TRACKER_INSTANCE"] = instance
    if instance == "PROD":
        os.environ["TRACKER_PROD_PARITY523"] = "1"
    if settings.get("TRACKER_DATA_DIR"):
        os.environ["TRACKER_DATA_DIR"] = settings["TRACKER_DATA_DIR"]

    from app import session_auth385 as auth

    if not auth.enabled():
        raise RuntimeError("Session authentication is disabled")

    source = auth.database_path()
    if not source.is_file() or source.is_symlink():
        raise RuntimeError("Invalid authentication database")

    password = getpass.getpass("New administrator password: ")
    confirm = getpass.getpass("Confirm new password: ")

    if password != confirm or not 12 <= len(password) <= 1024:
        raise ValueError("Passwords do not match or are too short")

    recovery_dir = Path("/tmp/tracker-backups")
    recovery_dir.mkdir(parents=True, exist_ok=True)

    backup = recovery_dir / (
        "auth-recovery-"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + f"-{os.getpid()}.sqlite3"
    )

    import sqlite3

    # SQLite backup API safely includes committed database state.
    with sqlite3.connect(str(source)) as live:
        with sqlite3.connect(str(backup)) as target:
            live.backup(target)

    os.chmod(backup, 0o600)
    original = source.stat()
    auth.recover_admin(password)
    # Root-operated recovery must not strand the service with root-owned
    # SQLite files/journals or an inaccessible auth store.
    for path in (source, Path(str(source) + "-wal"), Path(str(source) + "-shm")):
        if path.exists():
            if path.is_symlink():
                raise RuntimeError("Unsafe authentication sidecar symlink")
            os.chown(path, original.st_uid, original.st_gid)
            os.chmod(path, 0o600)

    print("PASS: Administrator password reset")
    print("PASS: All browser sessions revoked")
    print("Authentication backup:", backup)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
