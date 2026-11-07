#!/usr/bin/env python3
"""Release 445: disposable secondary-user recovery rehearsal (DEV only).

zip       Use --archive /path/to/tracker-secondary-....zip.
encrypted Use --encrypted-file PATH and --identity PATH, optionally SHA-256.

Restores only to a private temporary directory; clears copied admin/secondary
sessions, rotates copied CSRF key, validates users and uploads, then removes
the entire disposable environment. NO live restore or HTTP server startup.
Never put the age identity in the Tracker data directory.
"""

import argparse
import os
import sqlite3
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("zip", "encrypted"))
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--encrypted-file", type=Path)
    parser.add_argument("--identity", type=Path)
    parser.add_argument("--expected-sha256", type=str)
    parser.add_argument("--scratch-parent", type=Path)
    args = parser.parse_args()

    from app import config
    if os.geteuid() != 0 or config.instance_label() != "DEV":
        parser.error("Rehearsal requires root and explicit DEV instance")
    if args.mode == "zip":
        if (args.archive is None or args.encrypted_file is not None
            or args.identity is not None or args.expected_sha256 is not None):
            parser.error("ZIP rehearsal requires --archive alone")
    elif (args.encrypted_file is None or args.identity is None
          or args.archive is not None):
        parser.error("Encrypted rehearsal requires --encrypted-file and --identity")

    from app.secondary_restore_rehearsal445 import (
        rehearse_archive445, rehearse_encrypted_archive445,
    )
    try:
        if args.mode == "zip":
            result = rehearse_archive445(
                args.archive, scratch_parent=args.scratch_parent,
            )
        else:
            result = rehearse_encrypted_archive445(
                args.encrypted_file, identity=args.identity,
                expected_sha256=args.expected_sha256,
                scratch_parent=args.scratch_parent,
            )
        assert result["rehearsal_passed"] and result["sandbox_destroyed"]
        print("PASS: Disposable secondary recovery rehearsal")
        print("USERS_VERIFIED=" + str(result["private_databases_verified"]))
        print("PRIVATE_UPLOADS_VERIFIED=" + str(result["private_uploads_verified"]))
        print("ADMIN_SESSIONS_INVALIDATED=" + str(result["admin_sessions_invalidated"]))
        print("SECONDARY_SESSIONS_INVALIDATED=" + str(result["secondary_sessions_invalidated"]))
        print("SIGNING_KEY_ROTATED=YES")
        print("LIVE_DATA_MODIFIED=NO")
        print("SANDBOX_DESTROYED=YES")
        print("This is an offline rehearsal, not a live restore or a service-boot test.")
        return 0
    except (
        OSError, PermissionError, ValueError, RuntimeError,
        sqlite3.Error, zipfile.BadZipFile, subprocess.TimeoutExpired,
    ) as exc:
        # No archive contents, plaintext credentials or private paths in logs.
        print("FAIL: Recovery rehearsal: " + type(exc).__name__, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
