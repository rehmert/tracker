"""Read-only disaster-recovery audit for Tracker backup archives."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .backup import BACKUP_DIR, verify_backup


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def audit_archive(archive: Path, max_age_hours: float = 24) -> dict:
    archive = Path(archive).resolve(strict=True)

    if max_age_hours <= 0:
        raise ValueError("Maximum backup age must be positive")

    # Reuse Tracker's existing checksum and database verification.
    manifest = verify_backup(archive)

    age_hours = (
        datetime.now(timezone.utc).timestamp()
        - archive.stat().st_mtime
    ) / 3600

    if age_hours < 0:
        raise ValueError("Backup modification time is in the future")

    with tempfile.TemporaryDirectory(
        prefix="tracker-recovery-"
    ) as temporary:
        destination = Path(temporary)
        restored = []

        with zipfile.ZipFile(archive) as source:
            for name, metadata in manifest["files"].items():
                relative = Path(name)

                if (
                    relative.is_absolute()
                    or ".." in relative.parts
                    or "\\" in name
                    or name == "manifest.json"
                ):
                    raise ValueError(f"Unsafe backup entry: {name}")

                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)

                # Extract only explicitly verified manifest entries.
                with source.open(name) as src, target.open("wb") as dst:
                    import shutil
                    shutil.copyfileobj(src, dst)

                if target.stat().st_size != metadata["bytes"]:
                    raise ValueError(f"Restored size mismatch: {name}")

                if _sha256(target) != metadata["sha256"]:
                    raise ValueError(f"Restored checksum mismatch: {name}")

                restored.append(name)

        database = destination / "tracker.db"

        if not database.is_file():
            raise ValueError("Restored database missing")

        uri = f"file:{database.as_posix()}?mode=ro"

        with sqlite3.connect(uri, uri=True) as connection:
            integrity = connection.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0]

            if integrity != "ok":
                raise ValueError(
                    f"Restored database integrity failure: {integrity}"
                )

            foreign_keys = connection.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()

            tables = connection.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type='table'
                AND name NOT LIKE 'sqlite_%'
                """
            ).fetchall()

        if not tables:
            raise ValueError("Restored database contains no user tables")

        if foreign_keys:
            raise ValueError(
                f"Restored database has {len(foreign_keys)} "
                "foreign-key violations"
            )

        result = {
            "archive": str(archive),
            "age_hours": round(age_hours, 2),
            "maximum_age_hours": max_age_hours,
            "fresh": age_hours <= max_age_hours,
            "files_restored": len(restored),
            "uploads_restored": sum(
                name.startswith("uploads/") for name in restored
            ),
            "database_tables": len(tables),
            "integrity": integrity,
            "foreign_key_violations": len(foreign_keys),
            "checksums_verified": True,
            "temporary_restore": "successful",
        }

    # TemporaryDirectory has now removed the restored copy.
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify Tracker backup recoverability"
    )

    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=BACKUP_DIR,
    )

    parser.add_argument(
        "--archive",
        type=Path,
        default=None,
    )

    parser.add_argument(
        "--max-age-hours",
        type=float,
        default=24,
    )

    args = parser.parse_args()

    try:
        if args.archive:
            archive = args.archive
        else:
            candidates = sorted(
                args.backup_dir.glob("tracker-*.zip"),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )

            if not candidates:
                raise FileNotFoundError(
                    f"No Tracker backups found in {args.backup_dir}"
                )

            archive = candidates[0]

        result = audit_archive(
            archive,
            max_age_hours=args.max_age_hours,
        )

        print(json.dumps(result, indent=2))

        if not result["fresh"]:
            print(
                "WARNING: Backup is older than the configured threshold"
            )
            return 2

        print("PASS: Backup recovery audit successful")
        return 0

    except Exception as exc:
        print(f"FAIL: Backup recovery audit: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
