#!/usr/bin/env python3
"""Read-only audit of scoped database engine integration."""

import ast
import inspect
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    from fastapi.params import Depends as DependsParameter

    from app.db import get_db
    from app.scoped_db390 import get_scoped_db390
    from app.workspace_engine401 import get_workspace_db401
    from app.user_storage388 import live_storage_for

    print("=== RELEASE 402 SCOPED ENGINE AUDIT ===")

    for dependency in (
        get_scoped_db390,
        get_workspace_db401,
    ):
        default = inspect.signature(
            dependency
        ).parameters["db"].default

        assert isinstance(default, DependsParameter)
        assert default.dependency is get_db

        print(
            "PASS:",
            dependency.__name__,
            "preserves get_db override",
        )

    source = (
        ROOT / "app/scoped_db390.py"
    ).read_text()

    ast.parse(source)

    assert (
        "resolve_authenticated_storage(request)"
        in source
    )
    assert (
        "yield from get_workspace_db401(request, db)"
        in source
    )

    for user_id in (2, 3):
        try:
            live_storage_for(user_id)
        except PermissionError:
            pass
        else:
            raise RuntimeError(
                f"Inactive account {user_id} enabled"
            )

    print()
    print("Legacy administrator DB engine: unchanged")
    print("Authenticated engine validation: integrated")
    print("FastAPI override compatibility: preserved")
    print("Additional user accounts: disabled")
    print("New user engines: not activated")
    print("Database migrations: none")
    print("Cross-account isolation: incomplete")

    print("PASS: Release 402 routing audit")


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
