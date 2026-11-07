#!/usr/bin/env python3
"""DEV-only private secondary recovery snapshot and isolated restore verification.

Usage:
  python scripts/tracker-secondary-backup442.py create [--backup-dir DIR]
  python scripts/tracker-secondary-backup442.py verify --archive FILE

Create and verify do not restore or overwrite any live user data.
This ZIP holds credential hashes and may hold an application signing key.
Protect the archive with encryption before transferring it off-host.
"""
import argparse
import os
import sqlite3
import sys
import zipfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("create", "verify"))
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()

    from app import config
    if config.instance_label() != "DEV":
        parser.error("Secondary backup commands are DEV-only")
    if os.geteuid() != 0:
        parser.error("Run as root to protect private recovery data")
    if args.action == "create" and args.archive is not None:
        parser.error("Create does not accept --archive")
    if args.action == "verify" and (args.archive is None or args.backup_dir is not None):
        parser.error("Verify requires --archive and no --backup-dir")

    from app.secondary_backup442 import (
        create_secondary_backup442, verify_secondary_backup442,
    )
    try:
        if args.action == "create":
            path = create_secondary_backup442(backup_dir=args.backup_dir)
            report = verify_secondary_backup442(path)
            print("PASS: Secondary snapshot created and isolated restore verified")
            print("ARCHIVE=" + str(path))
        else:
            report = verify_secondary_backup442(args.archive)
            print("PASS: Non-destructive isolated secondary restore verified")
        print(
            "Secondary users: " + str(report["user_count"])
            + "; files: " + str(report["files"])
            + "; recovered bytes: " + str(report["bytes"])
        )
        print("Consistency: per database, not one global atomic snapshot")
        print("SECURITY: Contains authentication data; encrypt for off-host storage")
        return 0
    except (OSError, RuntimeError, PermissionError, ValueError,
            KeyError, TypeError, UnicodeError, sqlite3.Error,
            zipfile.BadZipFile) as exc:
        print(
            "FAIL: Secondary recovery: "
            + type(exc).__name__ + ": " + str(exc)[:160],
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
