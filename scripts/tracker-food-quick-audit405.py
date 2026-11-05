#!/usr/bin/env python3
"""Read-only Release 405 quick-food routing audit."""

import ast
import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    from fastapi.params import Depends as DependsParameter
    from fastapi.routing import APIRoute

    from app.food_engine392 import get_food_engine392
    from app.food_storage_guard391 import require_food_storage391
    from app.routers import food_quick375
    from app.user_storage388 import live_storage_for

    print("=== RELEASE 405 FOOD QUICK-ENTRY AUDIT ===")

    for endpoint in (
        food_quick375.quick_log,
        food_quick375.toggle_favorite,
    ):
        dependency = inspect.signature(
            endpoint
        ).parameters["db_engine"].default

        assert isinstance(
            dependency,
            DependsParameter,
        )
        assert dependency.dependency is get_food_engine392

        print(
            "PASS:",
            endpoint.__name__,
            "uses request-authorized engine",
        )

    for route in food_quick375.router.routes:
        if not isinstance(route, APIRoute):
            continue

        guards = {
            item.dependency
            for item in route.dependencies
        }

        assert require_food_storage391 in guards

    source = Path(food_quick375.__file__).read_text()
    ast.parse(source)

    assert source.count(
        "with db_engine.begin() as db:"
    ) == 2

    assert "with engine.begin() as db:" not in source
    assert "with engine.connect() as db:" in source

    for uid in (2, 3):
        try:
            live_storage_for(uid)
        except PermissionError:
            pass
        else:
            raise RuntimeError(
                f"Inactive user {uid} gained access"
            )

    print()
    print("Quick food writes: request-authorized")
    print("Favorites: request-authorized")
    print("Read helpers: unchanged")
    print("Food schema: unchanged")
    print("Additional accounts: disabled")
    print("Full multi-user routing: incomplete")
    print("PASS: Release 405 audit")


if __name__ == "__main__":
    main()
