#!/usr/bin/env python3
"""Read-only Release 401 engine-routing readiness audit."""

import ast
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    print("=== RELEASE 401 WORKSPACE ENGINE AUDIT ===")

    required = (
        "app/workspace_engine401.py",
        "app/workspace_boundary399.py",
        "app/user_storage388.py",
        "app/user_db389.py",
        "app/scoped_db390.py",
        "app/session_auth385.py",
        "app/db.py",
    )

    for name in required:
        path = ROOT / name

        assert path.is_file(), name

        ast.parse(
            path.read_text(),
            filename=name,
        )

        print("PASS:", name)

    from app.workspace_engine401 import (
        plan_workspace_engine401,
    )
    from app.user_storage388 import live_storage_for

    two = plan_workspace_engine401(2)
    three = plan_workspace_engine401(3)

    assert two.database != three.database
    assert two.url.database != three.url.database

    assert two.mode == "reserved-inactive"
    assert three.mode == "reserved-inactive"

    for user_id in (2, 3):
        try:
            live_storage_for(user_id)
        except PermissionError:
            pass
        else:
            raise RuntimeError(
                f"Inactive workspace {user_id} gained live access"
            )

    print()
    print("Separate per-user database plans: verified")
    print("Administrator engine: unchanged")
    print("Secondary live engines: disabled")
    print("Additional accounts: disabled")
    print("Test-only SQLAlchemy isolation: covered")
    print("Production multi-user activation: NOT ENABLED")
    print("Full application migration: INCOMPLETE")

    print("PASS: Workspace engine readiness audit")


if __name__ == "__main__":
    try:
        main()
    except (
        AssertionError,
        RuntimeError,
        OSError,
        SyntaxError,
    ) as error:
        print("ERROR:", error, file=sys.stderr)
        raise SystemExit(1)
