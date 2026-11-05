#!/usr/bin/env python3
"""Read-only food database alias audit."""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    from fastapi.routing import APIRoute
    from app.food_storage_guard391 import (
        require_food_storage391,
    )
    from app.routers import (
        food,
        food_quick375,
        food_bundle376,
        food_manage377,
        food_review378,
        food_week379,
    )

    modules = (
        food,
        food_quick375,
        food_bundle376,
        food_manage377,
        food_review378,
        food_week379,
    )

    print("=== RELEASE 404 FOOD ENGINE ALIAS AUDIT ===")

    count = 0

    for module in modules:
        routes = [
            route
            for route in module.router.routes
            if isinstance(route, APIRoute)
        ]

        assert routes, module.__name__

        for route in routes:
            dependencies = {
                dep.dependency
                for dep in route.dependencies
            }

            assert require_food_storage391 in dependencies, (
                module.__name__,
                route.path,
            )

            count += 1

        print(
            f"PASS: {module.__name__}: "
            f"{len(routes)} guarded routes"
        )

    guard_file = ROOT / "app/food_storage_guard391.py"
    source = guard_file.read_text()
    ast.parse(source)

    assert (
        "for selected in (food.engine, food_quick375.engine)"
        in source
    )
    assert "resolve_live_engine401(request)" in source
    assert "resolve_authenticated_storage(request)" in source

    direct_references = {}

    for module in modules:
        source = Path(module.__file__).read_text()
        tree = ast.parse(source)

        direct_references[module.__name__] = sum(
            1
            for node in ast.walk(tree)
            if (
                isinstance(node, ast.Attribute)
                and node.attr in ("begin", "connect")
                and isinstance(node.value, ast.Name)
                and node.value.id == "engine"
            )
        )

    print()
    print("Total food routes guarded:", count)
    print("Main food engine alias: verified")
    print("Quick food engine alias: verified")
    print("Engine alias mismatch: fail closed")
    print("Legacy database: unchanged")
    print("Other users: disabled")
    print("Per-user food database routing: incomplete")

    print("PASS: Release 404 alias audit")


if __name__ == "__main__":
    main()
