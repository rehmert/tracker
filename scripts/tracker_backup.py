#!/usr/bin/env python3
"""Run from project root: python -m scripts.tracker_backup [create|verify|list].

Scheduled 'create' now requires a full isolated restore before pruning and
records a private, point-in-time recovery receipt for the newest archive.
"""
import argparse
from pathlib import Path
import subprocess
import sys

from app.backup import create_backup, list_backups, prune_backups, verify_backup
from app.background_storage410 import administrator_context410


def verify_restorable(archive: Path) -> None:
    tool = Path(__file__).resolve().with_name("tracker-restore-verify.py")
    # Run outside the web request path, using the timer's service identity.
    # If verification fails, keep the archive and refuse to prune backups.
    subprocess.run(
        [sys.executable, str(tool), "--archive", str(archive), "--record-status"],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        timeout=1800,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["create", "verify", "list", "context-check"])
    parser.add_argument("archive", nargs="?")
    args = parser.parse_args()
    if args.action == "context-check":
        context = administrator_context410()
        print("PASS: Administrator storage context valid")
        print("Scope:", context.scope)
        print("Database:", context.database)
        print("Data directory:", context.data_dir)
        print("Archive directory:", context.backup_dir)
    elif args.action == "create":
        archive = create_backup()
        print(f"Created and verified {archive}", flush=True)
        verify_restorable(archive)
        print("PASS: Scheduled backup passed isolated restore", flush=True)
        print(f"Pruned {len(prune_backups())} old backups")
    elif args.action == "verify":
        if not args.archive:
            parser.error("verify requires archive path")
        manifest = verify_backup(Path(args.archive))
        print(f"Verified {len(manifest['files'])} files")
    else:
        for item in list_backups():
            print(f"{item['modified'].isoformat()} {item['size']:>12} {item['name']}")


if __name__ == "__main__":
    main()
