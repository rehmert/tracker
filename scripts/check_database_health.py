#!/usr/bin/env python3

import os
import sqlite3
from pathlib import Path

ROOT = Path("/opt/tracker")

SEARCH_PATHS = [
    ROOT / "data",
    ROOT / "backups",
    Path("/tracker-backups"),
]

def check_database(path):
    print(f"\nChecking: {path}")

    try:
        uri = f"{path.resolve().as_uri()}?mode=ro"

        with sqlite3.connect(uri, uri=True, timeout=10) as db:
            integrity = db.execute(
                "PRAGMA integrity_check"
            ).fetchall()

            foreign_keys = db.execute(
                "PRAGMA foreign_key_check"
            ).fetchall()

            print(
                "Integrity:",
                "OK" if integrity == [("ok",)] else integrity
            )

            print(
                "Foreign keys:",
                "OK" if not foreign_keys else
                f"{len(foreign_keys)} violations"
            )

            return (
                integrity == [("ok",)]
                and not foreign_keys
            )

    except Exception as exc:
        print("ERROR:", exc)
        return False

def main():
    databases = []

    for directory in SEARCH_PATHS:
        if not directory.is_dir():
            continue

        databases.extend(directory.rglob("*.db"))
        databases.extend(directory.rglob("*.sqlite"))
        databases.extend(directory.rglob("*.sqlite3"))

    databases = sorted(set(databases))

    if not databases:
        print("No SQLite databases found.")
        return 2

    failed = 0

    for database in databases:
        if not check_database(database):
            failed += 1

    print()
    print("Databases checked:", len(databases))
    print("Failed checks:", failed)

    return 1 if failed else 0

if __name__ == "__main__":
    raise SystemExit(main())
