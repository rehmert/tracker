#!/usr/bin/env python3
"""Release 444: DEV-only encrypted secondary backup export and restore rehearsal.

export   Independently verify a local secondary ZIP, encrypt to an age1
         recipient public key and publish a private .age file. NO upload.
rehearse Decrypt the .age file to an isolated temporary directory using an
         existing identity file and verify its restored files and databases.
         NEVER writes the live Tracker data directory.

Generate and keep the age private identity OFF this server. For a decryption
rehearsal, temporarily mount it only on an isolated DEV recovery host.
This tool NEVER generates, copies, exports or logs the private identity.
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
    parser.add_argument("action", choices=("export", "rehearse"))
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--export-dir", type=Path)
    parser.add_argument("--recipient", type=str)
    parser.add_argument("--encrypted-file", type=Path)
    parser.add_argument("--identity", type=Path)
    parser.add_argument("--expected-sha256", type=str)
    args = parser.parse_args()

    from app import config
    if os.geteuid() != 0 or config.instance_label() != "DEV":
        parser.error("Encrypted recovery export/rehearsal requires DEV root")

    if args.action == "export":
        if not args.recipient or any((
            args.encrypted_file is not None,
            args.identity is not None,
            args.expected_sha256 is not None,
        )):
            parser.error("Export requires --recipient; no identity or encrypted input")
    else:
        if (args.encrypted_file is None or args.identity is None or any((
            args.recipient is not None,
            args.archive is not None,
            args.backup_dir is not None,
            args.export_dir is not None,
        ))):
            parser.error("Rehearse requires --encrypted-file and --identity")

    from app.secondary_encrypted_export444 import (
        export_encrypted444, rehearse_encrypted444,
    )
    try:
        if args.action == "export":
            report = export_encrypted444(
                args.archive,
                recipient=args.recipient,
                backup_dir=args.backup_dir,
                export_dir=args.export_dir,
            )
            print("PASS: Release 442 source archive verified and encrypted")
            print("ENCRYPTED_FILE=" + report["encrypted_file"])
            print("SHA256=" + report["encrypted_sha256"])
            print("USERS=" + str(report["user_count"]))
            print("Encrypted export has NOT been uploaded or decrypted for rehearsal")
        else:
            report = rehearse_encrypted444(
                args.encrypted_file,
                identity=args.identity,
                expected_sha256=args.expected_sha256,
            )
            print("PASS: Encrypted archive decrypted, isolated restore verified")
            print("SHA256=" + report["encrypted_sha256"])
            print("USERS=" + str(report["user_count"]))
            print("LIVE_DATA_MODIFIED=NO")
        return 0
    except (
        OSError, PermissionError, ValueError, RuntimeError,
        subprocess.TimeoutExpired, sqlite3.Error, zipfile.BadZipFile,
    ) as exc:
        print(
            "FAIL: Encrypted recovery operation: " + type(exc).__name__,
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
