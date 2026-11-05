#!/usr/bin/env python3
"""Read-only, application-wide multi-user migration inventory.

Source route declarations and runtime route registration are
separate metrics. Neither proves completed isolation.

The report is a migration checklist, not an access grant.
"""

import argparse
import ast
import json
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


GLOBAL_PATH_ATTRIBUTES = {
    "DB_PATH",
    "DB_URL",
    "DATA_DIR",
    "UPLOAD_DIR",
    "LAB_DIR",
    "BACKUP_DIR",
}

FILESYSTEM_FUNCTIONS = {
    "open",
    "unlink",
    "mkdir",
    "rmdir",
    "rename",
    "replace",
    "read_bytes",
    "write_bytes",
    "read_text",
    "write_text",
}

HTTP_DECORATORS = {
    "get", "post", "put", "patch",
    "delete", "head", "options", "api_route",
    "websocket",
}


def dotted(node):
    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Attribute):
        parent = dotted(node.value)
        return parent + "." + node.attr if parent else node.attr

    return ""


def source_routes(path, tree):
    """Discover source declarations without importing route modules."""
    routes = []

    for node in ast.walk(tree):
        if not isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            continue

        for decorator in node.decorator_list:
            call = decorator if isinstance(
                decorator, ast.Call
            ) else None

            if call is None:
                continue

            target = dotted(call.func)
            parts = target.split(".")

            if len(parts) != 2:
                continue

            owner, method = parts

            if owner not in ("router", "app"):
                continue

            if method not in HTTP_DECORATORS:
                continue

            route_path = None

            if call.args:
                arg = call.args[0]
                if isinstance(arg, ast.Constant):
                    if isinstance(arg.value, str):
                        route_path = arg.value

            if route_path is None:
                for keyword in call.keywords:
                    if (
                        keyword.arg == "path"
                        and isinstance(
                            keyword.value, ast.Constant
                        )
                        and isinstance(
                            keyword.value.value, str
                        )
                    ):
                        route_path = keyword.value.value

            routes.append({
                "module": path.relative_to(ROOT).as_posix(),
                "function": node.name,
                "method_decorator": method.upper(),
                "path": route_path,
                "line": node.lineno,
                "source_declaration_only": True,
            })

    return routes


def scan_module(path):
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))

    tags = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "sqlite3":
                    tags.add("sqlite3_import")

                if alias.name in (
                    "os", "shutil", "subprocess"
                ):
                    tags.add("system_or_filesystem_import")

        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = {item.name for item in node.names}

            if module == "db" and node.level:
                if "engine" in names:
                    tags.add("global_engine_import")
                if "SessionLocal" in names:
                    tags.add("direct_session_factory")
                if "get_db" in names:
                    tags.add("legacy_db_import")

            if "UploadFile" in names:
                tags.add("upload_handler")

            if "FileResponse" in names:
                tags.add("file_response")

        elif isinstance(node, ast.Attribute):
            if (
                node.attr in GLOBAL_PATH_ATTRIBUTES
                and dotted(node.value) in (
                    "config", "backup", "db", "food"
                )
            ):
                tags.add("global_data_path")

        elif isinstance(node, ast.Call):
            target = dotted(node.func)
            name = target.rsplit(".", 1)[-1]

            if target == "sqlite3.connect":
                tags.add("direct_sqlite_connection")

            if target in (
                "engine.begin",
                "engine.connect",
                "food.engine.begin",
                "food.engine.connect",
            ):
                tags.add("global_engine_operation")

            if name in FILESYSTEM_FUNCTIONS:
                tags.add("filesystem_operation_candidate")

            if name in (
                "create_backup",
                "verify_backup",
                "verify_restorable",
                "restore_backup",
            ):
                tags.add("backup_restore_candidate")

    if "Depends(get_db)" in source:
        tags.add("legacy_db_dependency_used")

    if "Depends(get_scoped_db390)" in source:
        tags.add("scoped_db_dependency_used")

    if "Depends(get_food_engine392)" in source:
        tags.add("scoped_food_engine_used")

    return {
        "path": path.relative_to(ROOT).as_posix(),
        "signals": sorted(tags),
        "routes": source_routes(path, tree),
    }


def declared_global_auth():
    """Check the actual FastAPI constructor in app/main.py."""
    path = APP / "main.py"
    tree = ast.parse(path.read_text(), filename=str(path))

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue

        if not any(
            isinstance(target, ast.Name)
            and target.id == "app"
            for target in node.targets
        ):
            continue

        call = node.value
        if not isinstance(call, ast.Call):
            continue

        if dotted(call.func) != "FastAPI":
            continue

        for keyword in call.keywords:
            if keyword.arg != "dependencies":
                continue

            value = keyword.value

            if not isinstance(value, (ast.List, ast.Tuple)):
                continue

            for element in value.elts:
                if not isinstance(element, ast.Call):
                    continue

                if dotted(element.func) != "Depends":
                    continue

                if (
                    len(element.args) == 1
                    and dotted(element.args[0]) == "require_auth"
                ):
                    return True

    return False


def runtime_route_count():
    """Diagnostic only: not used as the source coverage count."""
    from fastapi.routing import APIRoute
    from app.main import app

    routes = [
        route for route in app.routes
        if isinstance(route, APIRoute)
    ]

    return len(routes)


def build_inventory():
    modules = [
        scan_module(path)
        for path in sorted(APP.rglob("*.py"))
    ]

    declarations = [
        entry
        for module in modules
        for entry in module["routes"]
    ]

    return {
        "release": "393.1",
        "status": "migration-in-progress",
        "multi_user_enabled": False,
        "application_isolation_complete": False,
        "source_module_count": len(modules),
        "source_route_declaration_count": len(declarations),
        "runtime_registered_route_count": runtime_route_count(),
        "global_auth_declared": declared_global_auth(),
        "global_auth_coverage_proven": False,
        "modules": modules,
        "source_route_declarations": declarations,
        "priority_workstreams": [
            "All database sessions and direct engine access",
            "All SQLite viewer and direct SQLite operations",
            "All upload and attachment storage",
            "All reports, downloads, exports and data extraction",
            "All backups, recovery and restore operations",
            "All background jobs and scheduled operations",
            "All per-user preferences and configuration",
            "Full cross-account isolation tests",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    report = build_inventory()

    counts = Counter()

    for module in report["modules"]:
        counts.update(module["signals"])

    print("=== RELEASE 393.1 ISOLATION INVENTORY ===")
    print(
        "Python modules:",
        report["source_module_count"],
    )
    print(
        "Source route declarations:",
        report["source_route_declaration_count"],
    )
    print(
        "Runtime registered routes (diagnostic):",
        report["runtime_registered_route_count"],
    )
    print(
        "Global auth declared:",
        report["global_auth_declared"],
    )
    print("Global auth coverage proven: NO")

    print()
    print("Source access signals:")

    for name, count in sorted(counts.items()):
        print(f"  {name}: {count} modules")

    print()
    print("Priority module findings:")

    priority = (
        "app/routers/food",
        "app/routers/labs",
        "app/routers/coas",
        "app/routers/backups",
        "app/routers/sqlite_viewer",
        "app/routers/exports",
        "app/backup",
        "app/db",
    )

    for module in report["modules"]:
        if module["path"].startswith(priority):
            print(
                " ",
                module["path"],
                ":",
                ", ".join(module["signals"])
                or "no flagged signals",
            )

    print()
    print("MULTI-USER ISOLATION: INCOMPLETE")
    print("ADDITIONAL USER ACCOUNTS: DISABLED")
    print("EXISTING ADMINISTRATOR DATABASE: UNCHANGED")

    if args.json:
        args.json.parent.mkdir(
            parents=True, exist_ok=True
        )
        args.json.write_text(
            json.dumps(report, indent=2) + "\n"
        )
        print("JSON inventory:", args.json)

    if not report["global_auth_declared"]:
        raise RuntimeError(
            "Application-wide auth dependency not found"
        )

    if report["source_route_declaration_count"] < 50:
        raise RuntimeError(
            "Source route inventory unexpectedly small"
        )

    if report["runtime_registered_route_count"] < 2:
        raise RuntimeError(
            "Application runtime inventory unavailable"
        )

    print("PASS: Source inventory and auth declaration verified")


if __name__ == "__main__":
    try:
        main()
    except (
        OSError,
        ValueError,
        RuntimeError,
        SyntaxError,
    ) as error:
        print("ERROR:", error, file=sys.stderr)
        raise SystemExit(1)
