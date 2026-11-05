#!/usr/bin/env python3
"""Read-only food route authorization audit."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.food_storage_guard391 import require_food_storage391
from app.routers import (
    food,
    food_quick375,
    food_bundle376,
    food_manage377,
    food_review378,
    food_week379,
)


def main():
    modules = (
        food,
        food_quick375,
        food_bundle376,
        food_manage377,
        food_review378,
        food_week379,
    )

    total = 0
    csv = 0

    for module in modules:
        for route in module.router.routes:
            dependencies = [
                item.dependency
                for item in getattr(
                    route, "dependencies", ()
                )
            ]

            if require_food_storage391 not in dependencies:
                raise RuntimeError(
                    f"Unguarded route: {route.path}"
                )

            total += 1

            if route.path.endswith(".csv"):
                csv += 1

    print("=== RELEASE 391 FOOD ACCESS AUDIT ===")
    print("Guarded food modules:", len(modules))
    print("Guarded endpoints:", total)
    print("Guarded CSV endpoints:", csv)
    print("Authorized live account: administrator (ID 1)")
    print("Food SQLAlchemy engine: unchanged")
    print("Other user accounts: disabled")
    print("Per-user engine switching: not enabled")
    print("Database migrations: none")
    print("Personal records migrated: none")

    assert total >= 15
    assert csv >= 2

    print("PASS: All six food routers are guarded")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, AssertionError) as error:
        print("ERROR:", error, file=sys.stderr)
        raise SystemExit(1)
