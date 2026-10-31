#!/usr/bin/env python3

"""Tracker development preflight and source snapshot."""

import argparse
import datetime
import hashlib
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
BACKUPS = pathlib.Path("/tmp/tracker-backups")

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
    "backups",
}

EXCLUDE_SUFFIXES = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".pyc",
}

SOURCE_SUFFIXES = {
    ".py",
    ".html",
    ".js",
    ".css",
    ".sh",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
    ".ini",
}


def git(*args):
    return subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def source_files():
    roots = [
        ROOT / "app",
        ROOT / "scripts",
        ROOT / "tests",
    ]

    result = []

    for base in roots:
        if not base.exists():
            continue

        for path in base.rglob("*"):
            if not path.is_file():
                continue

            relative = path.relative_to(ROOT)

            if any(
                part in EXCLUDE_DIRS
                for part in relative.parts
            ):
                continue

            if path.suffix in EXCLUDE_SUFFIXES:
                continue

            if path.suffix not in SOURCE_SUFFIXES:
                continue

            if path.is_symlink():
                continue

            result.append(path)

    return sorted(set(result))


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--snapshot",
        action="store_true",
        help="Create a source snapshot",
    )

    parser.add_argument(
        "--json",
        dest="json_path",
        help="Write preflight report",
    )

    parser.add_argument(
        "--require-clean",
        action="store_true",
        help="Require no tracked modifications",
    )

    args = parser.parse_args()

    status = git("status", "--porcelain", "-z")

    if status.returncode:
        print(
            "ERROR: Cannot read Git status",
            file=sys.stderr,
        )
        return 2

    entries = [
        item
        for item in status.stdout.split("\0")
        if item
    ]

    # Git porcelain entries starting with ?? are
    # untracked files. These are not automatically
    # treated as installation blockers.

    tracked_changes = [
        item
        for item in entries
        if not item.startswith("??")
    ]

    untracked = [
        item
        for item in entries
        if item.startswith("??")
    ]

    files = source_files()

    report = {
        "timestamp": datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat(),
        "repository": str(ROOT),
        "source_files": len(files),
        "tracked_changes": tracked_changes,
        "untracked_files": untracked,
        "snapshot": None,
        "checksums": {},
    }

    print("Tracker Development Preflight")
    print("-----------------------------")
    print("Source files:", len(files))
    print("Tracked changes:", len(tracked_changes))
    print("Untracked entries:", len(untracked))

    if tracked_changes:
        print()
        print("Tracked changes detected:")

        for item in tracked_changes[:30]:
            print(" ", item)

    if untracked:
        print()
        print("Untracked files are allowed.")

    if args.require_clean and tracked_changes:
        print(
            "ERROR: Tracked changes exist.",
            file=sys.stderr,
        )
        return 1

    if args.snapshot:
        timestamp = datetime.datetime.now(
            datetime.timezone.utc
        ).strftime("%Y%m%d-%H%M%S-%f")

        destination = (
            BACKUPS / f"source-{timestamp}"
        )

        destination.mkdir(
            parents=True,
            exist_ok=False,
        )

        manifest = {}

        for path in files:
            relative = path.relative_to(ROOT)

            target = destination / relative

            target.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            data = path.read_bytes()

            target.write_bytes(data)

            manifest[str(relative)] = {
                "sha256": sha256(data),
                "bytes": len(data),
            }

        manifest_path = (
            destination / "manifest.json"
        )

        manifest_path.write_text(
            json.dumps(
                {
                    "repository": str(ROOT),
                    "created_at": report["timestamp"],
                    "files": manifest,
                },
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )

        report["snapshot"] = str(destination)
        report["checksums"] = manifest

        print()
        print("Snapshot created:")
        print(destination)
        print("Files backed up:", len(manifest))

        # Verify every copied file against its
        # recorded source checksum.

        for relative, metadata in manifest.items():
            copied = (
                destination / relative
            ).read_bytes()

            if sha256(copied) != metadata["sha256"]:
                print(
                    "ERROR: Snapshot checksum mismatch:",
                    relative,
                    file=sys.stderr,
                )
                return 1

        print("PASS: Snapshot checksums verified")

    if args.json_path:
        target = pathlib.Path(
            args.json_path
        )

        target.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        target.write_text(
            json.dumps(report, indent=2) + "\n",
            encoding="utf-8",
        )

        print("Report:", target)

    print()
    print("PASS: Preflight completed")

    return 0


if __name__ == "__main__":
    sys.exit(main())
