#!/usr/bin/env python3
"""Read-only application database-routing progress audit.

Reports converted FastAPI database dependencies.
Does not claim complete cross-account isolation.
"""

import ast
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUTERS = ROOT / "app/routers"

CORE = {
    "dashboard",
    "doses",
    "vitals",
    "compounds",
    "protocols",
    "vials",
    "purchases",
    "supplies",
    "calendar",
}

BATCH = {
    "pk": 53,
    "vendor_prices": 18,
    "blends": 9,
    "pages": 12,
    "reliability": 7,
    "search": 1,
    "inventory_intelligence": 2,
    "health_timeline": 2,
    "health_insights": 1,
    "exports": 1,
    "activity": 1,
    "inventory_timeline": 1,
}


def scan(path):
    tree = ast.parse(
        path.read_text(),
        filename=str(path),
    )

    counts = Counter()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        if not isinstance(node.func, ast.Name):
            continue

        if node.func.id != "Depends" or not node.args:
            continue

        target = node.args[0]

        if isinstance(target, ast.Name):
            counts[target.id] += 1

    return counts


def main():
    module_counts = {}

    for path in sorted(ROUTERS.glob("*.py")):
        module_counts[path.stem] = scan(path)

    scoped_total = 0
    legacy_total = 0

    print("=== RELEASE 395 APPLICATION ROUTING AUDIT ===")

    for name, counts in sorted(module_counts.items()):
        scoped = counts["get_scoped_db390"]
        legacy = counts["get_db"]

        scoped_total += scoped
        legacy_total += legacy

        if scoped or legacy:
            print(
                f"{name:32s} scoped={scoped:3d} "
                f"legacy={legacy:3d}"
            )

    print()
    print("Scoped dependencies:", scoped_total)
    print("Legacy get_db dependencies:", legacy_total)

    for name in CORE:
        counts = module_counts[name]

        if (
            counts["get_scoped_db390"] == 0
            or counts["get_db"] != 0
        ):
            raise RuntimeError(
                f"Previously converted feature regressed: {name}"
            )

    for name, expected in BATCH.items():
        counts = module_counts[name]

        if (
            counts["get_scoped_db390"] != expected
            or counts["get_db"] != 0
        ):
            raise RuntimeError(
                f"Release 395 routing mismatch: {name}"
            )

    if scoped_total < 160:
        raise RuntimeError(
            "Application scoped dependency count regressed"
        )

    print()
    print("Additional user accounts: DISABLED")
    print("Per-user database routing: NOT YET ENABLED")
    print("Direct engine access: REMAINS")
    print("Uploads and attachments: NOT FULLY ISOLATED")
    print("Backups and restore: NOT FULLY ISOLATED")
    print("Application-wide isolation: INCOMPLETE")

    print("PASS: Release 395 database routing audit")


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
