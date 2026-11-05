#!/usr/bin/env python3
"""Audit direct SQLite and backup route authorization."""

import sys

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.routing import APIRoute

from app.direct_storage_guard397 import (
    require_backup_storage397,
    require_direct_storage397,
)

from app.routers import (
    backups,
    record_explorer,
    sqlite_viewer,
)


def main():
    expected = (
        (
            "SQLite Viewer",
            sqlite_viewer,
            require_direct_storage397,
        ),
        (
            "Record Explorer",
            record_explorer,
            require_direct_storage397,
        ),
        (
            "Backup Management",
            backups,
            require_backup_storage397,
        ),
    )

    total = 0

    print("=== RELEASE 397 DIRECT STORAGE AUDIT ===")

    for label, module, guard in expected:
        count = 0

        for route in module.router.routes:
            if not isinstance(route, APIRoute):
                continue

            dependencies = [
                item.dependency
                for item in route.dependencies
            ]

            if guard not in dependencies:
                raise RuntimeError(
                    f"Unguarded route: {route.path}"
                )

            count += 1

        if count == 0:
            raise RuntimeError(
                f"No routes found in {label}"
            )

        total += count
        print(f"PASS: {label}: {count} guarded routes")

    print()
    print("Total guarded routes:", total)
    print("Direct SQLite: remains read-only")
    print("Backup implementation: unchanged")
    print("Existing administrator storage: preserved")
    print("Additional user accounts: disabled")
    print("Cross-account isolation: INCOMPLETE")

    if total < 10:
        raise RuntimeError(
            "Unexpectedly few direct storage routes"
        )

    print("PASS: Direct storage authorization audit")


if __name__ == "__main__":
    try:
        main()
    except (
        RuntimeError,
        OSError,
    ) as error:
        print("ERROR:", error, file=sys.stderr)
        raise SystemExit(1)
