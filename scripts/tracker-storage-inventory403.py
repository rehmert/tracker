#!/usr/bin/env python3
"""Read-only inventory of global storage access candidates.

Scans application modules and scripts without opening
databases or modifying files.

This is a review inventory. A reported occurrence does not
necessarily represent a vulnerability, and a clean scan
would not alone establish multi-user safety.
"""

import ast
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

SEARCH_ROOTS = (
    ROOT / "app",
    ROOT / "scripts",
)

STORAGE_ATTRIBUTES = {
    "DATA_DIR",
    "DB_URL",
    "DB_PATH",
    "UPLOAD_DIR",
    "LAB_DIR",
    "BACKUP_DIR",
}

CONNECTION_METHODS = {
    "connect",
    "begin",
    "create_engine",
    "SessionLocal",
}


def scan(path):
    tree = ast.parse(
        path.read_text(),
        filename=str(path),
    )

    findings = defaultdict(set)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "sqlite3":
                    findings["sqlite3_import"].add(
                        node.lineno
                    )

        if isinstance(node, ast.Call):
            func = node.func

            if isinstance(func, ast.Attribute):
                if func.attr in CONNECTION_METHODS:
                    findings["connection_candidate"].add(
                        node.lineno
                    )

                if (
                    isinstance(func.value, ast.Name)
                    and func.value.id == "sqlite3"
                    and func.attr == "connect"
                ):
                    findings["direct_sqlite"].add(
                        node.lineno
                    )

                if (
                    isinstance(func.value, ast.Name)
                    and func.value.id == "engine"
                    and func.attr in ("connect", "begin")
                ):
                    findings["global_engine"].add(
                        node.lineno
                    )

            if (
                isinstance(func, ast.Name)
                and func.id == "SessionLocal"
            ):
                findings["session_factory"].add(
                    node.lineno
                )

        if isinstance(node, ast.Attribute):
            if node.attr in STORAGE_ATTRIBUTES:
                findings["global_path_candidate"].add(
                    node.lineno
                )

    return findings


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

    print("=== RELEASE 403 GLOBAL STORAGE AUDIT ===")

    food_modules = (
        food,
        food_quick375,
        food_bundle376,
        food_manage377,
        food_review378,
        food_week379,
    )

    guarded_routes = 0

    for module in food_modules:
        routes = [
            route
            for route in module.router.routes
            if isinstance(route, APIRoute)
        ]

        if not routes:
            raise RuntimeError(
                f"Missing food routes: {module.__name__}"
            )

        for route in routes:
            dependencies = {
                dep.dependency
                for dep in route.dependencies
            }

            if require_food_storage391 not in dependencies:
                raise RuntimeError(
                    f"Unguarded food route: {route.path}"
                )

            guarded_routes += 1

    print(
        f"PASS: {guarded_routes} food routes "
        "retain administrator storage authorization"
    )

    source = (
        ROOT / "app/food_storage_guard391.py"
    ).read_text()

    required = (
        "resolve_authenticated_storage(request)",
        "resolve_live_engine401(request)",
        "food.engine is not administrator_engine",
    )

    for expression in required:
        if expression not in source:
            raise RuntimeError(
                f"Missing food engine check: {expression}"
            )

    print("PASS: Food session and engine checks verified")

    findings_total = defaultdict(int)
    candidates = []

    for folder in SEARCH_ROOTS:
        for path in sorted(folder.rglob("*.py")):
            findings = scan(path)

            relevant = {
                key: sorted(lines)
                for key, lines in findings.items()
                if lines
            }

            if not relevant:
                continue

            relative = path.relative_to(ROOT).as_posix()
            candidates.append((relative, relevant))

            for key, lines in relevant.items():
                findings_total[key] += len(lines)

    print()
    print("=== GLOBAL STORAGE REVIEW CANDIDATES ===")

    for name, findings in candidates:
        details = ", ".join(
            f"{kind}={len(lines)}"
            for kind, lines in sorted(findings.items())
        )

        print(f"{name}: {details}")

    print()
    print("=== TOTALS ===")

    for kind in sorted(findings_total):
        print(f"{kind}: {findings_total[kind]}")

    print()
    print("Candidates are informational; manual review required")
    print("Secondary accounts: disabled")
    print("Administrator database: unchanged")
    print("Multi-user isolation: INCOMPLETE")
    print("Full background-job isolation: NOT YET VERIFIED")
    print("Filesystem and backup isolation: NOT YET COMPLETE")

    print("PASS: Release 403 storage inventory")


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
