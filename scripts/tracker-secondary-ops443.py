#!/usr/bin/env python3
"""Release 443: DEV-only secondary backup operations.

run      Create + independently restore-verify + prune (newest 14 by default).
status   Restore-verify newest backup; fail if missing, corrupt or stale.
prune    Explicit opt-in retention operation; never remove unverified backup.

No login activation, live restore, cloud upload, or automatic encryption.
Output paths identify sensitive credential/health archives; keep logs private.
"""

import argparse
import json
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
    parser.add_argument("action", choices=("run", "status", "prune"))
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--keep", type=int, default=14)
    parser.add_argument("--max-age-hours", type=int, default=36)
    args = parser.parse_args()

    from app import config
    if os.geteuid() != 0 or config.instance_label() != "DEV":
        parser.error("Secondary recovery operations require root on DEV")
    if args.keep < 2 or args.keep > 365:
        parser.error("Keep count must be 2–365")
    if args.max_age_hours < 1 or args.max_age_hours > 720:
        parser.error("Health threshold must be 1–720 hours")

    from app.secondary_backup_ops443 import (
        health443, prune443, run_backup443,
    )

    try:
        if args.action == "run":
            result = run_backup443(args.backup_dir, keep=args.keep)
            print("PASS: New secondary recovery snapshot verified")
            print("ARCHIVE=" + result["archive"])
            print("RETAINED=" + str(result["retained"]))
            print("PRUNED=" + str(len(result["pruned"])))
        elif args.action == "prune":
            removed = prune443(args.backup_dir, keep=args.keep)
            print("PASS: Retention complete; verified archives removed=" +
                  str(len(removed)))
        else:
            report = health443(
                args.backup_dir, max_age_hours=args.max_age_hours,
            )
            print(json.dumps(report, sort_keys=True))
            if not report["healthy"]:
                print("FAIL: No fresh verified secondary backup", file=sys.stderr)
                return 2
            print("PASS: Fresh secondary recovery archive restored and verified")
        return 0
    except (OSError, ValueError, RuntimeError, PermissionError,
            sqlite3.Error, zipfile.BadZipFile) as exc:
        print(
            "FAIL: Secondary backup operation: "
            + type(exc).__name__ + ": " + str(exc)[:160],
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
