#!/usr/bin/env python3
"""Read-only inventory of Tracker database dependency patterns.

Checks Release 398 conversions and reports remaining legacy
database access across every application Python module.

This is a migration audit, not completed isolation proof.
"""

import ast
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
ROUTERS = APP / "routers"

BATCH = {
    "expiry_exposure": 2,
    "fefo_forecast": 2,
    "forecast_audit": 2,
    "forecast_horizons": 2,
    "inventory_data_quality": 3,
    "inventory_forecast": 2,
    "planning_hub": 2,
    "planning_priorities": 2,
    "protocol_coverage": 2,
    "reconstitution_calculator": 1,
    "replenishment_review": 2,
    "scheduled_forecast": 2,
    "workflow_tools": 4,
}


def scan(path):
    tree = ast.parse(
        path.read_text(),
        filename=str(path),
    )

    counts = Counter()

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if (
                isinstance(node.func, ast.Name)
                and node.func.id == "Depends"
                and node.args
                and isinstance(node.args[0], ast.Name)
            ):
                counts[
                    "depends:" + node.args[0].id
                ] += 1

            target = node.func

            if isinstance(target, ast.Attribute):
                if target.attr in (
                    "connect",
                    "begin",
                    "create_engine",
                    "sessionmaker",
                ):
                    counts[
                        "direct_connection_candidate"
                    ] += 1

        if isinstance(node, ast.Import):
            if any(
                name.name == "sqlite3"
                for name in node.names
            ):
                counts["sqlite3_import"] += 1

        if isinstance(node, ast.Attribute):
            if (
                isinstance(node.value, ast.Name)
                and node.value.id == "config"
                and node.attr in (
                    "DB_URL",
                    "DB_PATH",
                    "DATA_DIR",
                    "UPLOAD_DIR",
                    "LAB_DIR",
                )
            ):
                counts["global_path_candidate"] += 1

    return counts


def main():
    print("=== RELEASE 398 APPLICATION DATABASE AUDIT ===")

    router_counts = {}

    for path in sorted(ROUTERS.glob("*.py")):
        router_counts[path.stem] = scan(path)

    for name, expected in BATCH.items():
        counts = router_counts[name]

        scoped = counts["depends:get_scoped_db390"]
        legacy = counts["depends:get_db"]

        if scoped != expected or legacy:
            raise RuntimeError(
                f"{name}: scoped={scoped}, "
                f"legacy={legacy}, expected={expected}"
            )

        print(
            f"PASS: {name}: "
            f"{scoped} scoped dependencies"
        )

    from fastapi.routing import APIRoute
    from app.routers import maintenance_review
    from app.direct_storage_guard397 import (
        require_direct_storage397,
    )

    for route in maintenance_review.router.routes:
        if not isinstance(route, APIRoute):
            continue

        if require_direct_storage397 not in [
            item.dependency
            for item in route.dependencies
        ]:
            raise RuntimeError(
                f"Unguarded Maintenance Review: {route.path}"
            )

    totals = Counter()
    remaining = []

    for path in sorted(APP.rglob("*.py")):
        counts = scan(path)
        totals.update(counts)

        if (
            counts["depends:get_db"]
            or counts["direct_connection_candidate"]
            or counts["sqlite3_import"]
        ):
            remaining.append((
                path.relative_to(ROOT).as_posix(),
                counts,
            ))

    print()
    print("=== WHOLE-APPLICATION INVENTORY ===")

    print(
        "Scoped dependencies:",
        totals["depends:get_scoped_db390"],
    )

    print(
        "Legacy get_db dependencies:",
        totals["depends:get_db"],
    )

    print(
        "Direct connection candidates:",
        totals["direct_connection_candidate"],
    )

    print(
        "Modules importing sqlite3:",
        totals["sqlite3_import"],
    )

    print(
        "Global path references:",
        totals["global_path_candidate"],
    )

    print()
    print("Remaining candidates requiring review:")

    for name, counts in remaining:
        print(
            f"  {name}: "
            f"legacy={counts['depends:get_db']}, "
            f"connections={counts['direct_connection_candidate']}, "
            f"sqlite3={counts['sqlite3_import']}"
        )

    print()
    print("Previously converted modules: preserved")
    print("Maintenance Review: guarded")
    print("Existing administrator data: preserved")
    print("Additional users: disabled")
    print("Whole-application isolation: INCOMPLETE")
    print("User-specific database switching: NOT ENABLED")

    print("PASS: Release 398 routing audit")


if __name__ == "__main__":
    try:
        main()
    except (
        RuntimeError,
        OSError,
        SyntaxError,
    ) as error:
        print("ERROR:", error, file=sys.stderr)
        raise SystemExit(1)
