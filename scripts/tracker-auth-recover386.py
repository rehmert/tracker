#!/usr/bin/env python3
"""Recover the sole DEV administrator from the local console."""

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

    if settings.get("TRACKER_INSTANCE", "").upper() != "DEV":
        raise RuntimeError("DEV identity required")

    os.environ["TRACKER_INSTANCE"] = "DEV"
    if settings.get("TRACKER_DATA_DIR"):
        os.environ["TRACKER_DATA_DIR"] = settings["TRACKER_DATA_DIR"]

    from app import session_auth385 as auth

    if not auth.enabled():
        raise RuntimeError("DEV session authentication is disabled")

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
    auth.recover_admin(password)

    print("PASS: Administrator password reset")
    print("PASS: All browser sessions revoked")
    print("Authentication backup:", backup)


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
