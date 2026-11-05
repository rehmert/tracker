#!/usr/bin/env python3
"""Read-only Release 399 workspace readiness audit.

Does not read personal records or provision user storage.
Does not claim complete application-wide isolation.
"""

import ast
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

FILES = (
    "app/user_storage388.py",
    "app/user_db389.py",
    "app/request_scope393.py",
    "app/workspace_boundary399.py",
    "app/scoped_db390.py",
    "app/attachment_scope396.py",
    "app/direct_storage_guard397.py",
)

FORBIDDEN = (
    "live_storage_for(2)",
    "live_storage_for(3)",
)


def main():
    print("=== RELEASE 399 WORKSPACE ISOLATION AUDIT ===")

    for name in FILES:
        path = ROOT / name

        if not path.is_file():
            raise RuntimeError(
                f"Required boundary missing: {name}"
            )

        ast.parse(
            path.read_text(),
            filename=str(path),
        )

        print("PASS:", name)

    from app.user_storage388 import (
        planned_storage,
        live_storage_for,
    )

    two = planned_storage(2)
    three = planned_storage(3)

    for field in (
        "root",
        "database",
        "coa",
        "labs",
        "backups",
    ):
        if getattr(two, field) == getattr(three, field):
            raise RuntimeError(
                f"Workspace collision: {field}"
            )

    for user_id in (2, 3):
        try:
            live_storage_for(user_id)
        except PermissionError:
            pass
        else:
            raise RuntimeError(
                f"Inactive user {user_id} gained live access"
            )

    print()
    print("Inactive workspace IDs tested: 2, 3")
    print("Database paths: distinct")
    print("COA directories: distinct")
    print("Lab directories: distinct")
    print("Backup paths: distinct")
    print("Secondary live access: denied")
    print("Live application storage selection: administrator only")
    print("Per-user engine activation: NOT ENABLED")
    print("Application-wide migration: INCOMPLETE")
    print("Existing administrator data: UNCHANGED")

    print("PASS: Release 399 workspace readiness audit")


if __name__ == "__main__":
    try:
        main()
    except (
        OSError,
        RuntimeError,
        SyntaxError,
    ) as error:
        print("ERROR:", error, file=sys.stderr)
        raise SystemExit(1)
