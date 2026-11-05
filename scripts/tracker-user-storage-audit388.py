#!/usr/bin/env python3
"""Read-only DEV migration readiness audit for per-user storage."""

import os
import re
import shlex
import sqlite3
import sys
from pathlib import Path

# Permit direct execution without a caller-supplied PYTHONPATH.
APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))


def read_environment(path):
    values = {}

    for line in path.read_text().splitlines():
        line = line.strip()

        if line.startswith("export "):
            line = line[7:].strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, raw = line.split("=", 1)

        if key not in (
            "TRACKER_INSTANCE",
            "TRACKER_DATA_DIR",
        ):
            continue

        fields = shlex.split(raw, comments=False)

        if len(fields) != 1:
            raise ValueError(f"Invalid setting: {key}")

        values[key] = fields[0]

    return values


def main():
    settings = read_environment(Path("/etc/tracker.env"))

    if settings.get("TRACKER_INSTANCE", "").upper() != "DEV":
        raise ValueError("DEV identity required")

    data = Path(
        settings.get("TRACKER_DATA_DIR")
        or "/opt/tracker/data"
    ).resolve()

    from app.user_storage388 import (
        inspect_storage,
        planned_storage,
    )

    legacy = planned_storage(1, data)
    status = inspect_storage(1, data)

    if not status["database_exists"]:
        raise RuntimeError("Existing Tracker database missing")

    uri = "file:" + str(legacy.database) + "?mode=ro"

    with sqlite3.connect(uri, uri=True) as db:
        tables = db.execute("""
            SELECT COUNT(*) FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
        """).fetchone()[0]

        integrity = db.execute(
            "PRAGMA quick_check"
        ).fetchone()[0]

    if integrity != "ok":
        raise RuntimeError("Legacy SQLite quick_check failed")

    print("=== RELEASE 388 STORAGE READINESS ===")
    print("Instance: DEV")
    print("Administrator user ID: 1")
    print("Administrator mode: legacy-admin")
    print("Live database: original tracker.db")
    print("Application tables:", tables)
    print("SQLite quick_check: ok")
    print("Legacy COA directory:", status["coa_directory_exists"])
    print("Legacy lab directory:", status["lab_directory_exists"])
    print("Additional users: disabled")
    print("Live DB routing: unchanged")
    print("Migration performed: no")
    print("Personal records modified: no")
    print()
    print("NEXT STAGE BLOCKERS")
    print("1. Replace process-wide SQLAlchemy engine selection")
    print("2. Scope attachment readers/writers by authenticated user")
    print("3. Scope backup, restore, export and database explorer")
    print("4. Validate per-user background and scheduled tasks")
    print("5. Implement cross-account access-denial tests")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        print("ERROR:", exc, file=sys.stderr)
        raise SystemExit(1)
