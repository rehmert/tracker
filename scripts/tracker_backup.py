#!/usr/bin/env python3
"""Run from project root: python -m scripts.tracker_backup [create|verify|list|context-check].

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
        # Validate all storage roots before any write begins.
        context = administrator_context410()

        archive = Path(create_backup(
            data_dir=context.data_dir,
            backup_dir=context.backup_dir,
        )).absolute()

        # Do not verify or prune a backup located outside the
        # administrator archive directory. Never follow an
        # unexpected archive symlink.
        if (
            archive.parent != context.backup_dir
            or archive.is_symlink()
            or not archive.is_file()
        ):
            raise ValueError(
                "Backup result is outside authorized archive storage"
            )

        print(f"Created and verified {archive}", flush=True)
        verify_restorable(archive)
        print(
            "PASS: Scheduled backup passed isolated restore",
            flush=True,
        )
        removed = prune_backups(
            backup_dir=context.backup_dir,
        )
        print(f"Pruned {len(removed)} old backups")
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
