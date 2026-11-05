#!/usr/bin/env python3
"""Release 409: read-only source inventory of background storage.

This inventory does not run backup, restore, replication,
maintenance, or any database operations.

It distinguishes:
- browser endpoints guarded by administrator authorization;
- process-wide storage defaults;
- non-request executable entry points;
- source operations that require future isolation review.

A reported candidate does not prove a vulnerability.
This inventory does not certify multi-user isolation.
"""

import argparse
import ast
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

PYTHON_TARGETS = {
    "backup_library": "app/backup.py",
    "backup_entrypoint": "scripts/tracker_backup.py",
    "restore_verifier": "scripts/tracker-restore-verify.py",
    "replication_entrypoint": "scripts/tracker_replica.py",
    "maintenance_entrypoint": "scripts/tracker_db_maintenance.py",
    "recovery_audit": "app/backup_recovery.py",
    "backup_router": "app/routers/backups.py",
    "maintenance_router": "app/routers/maintenance_review.py",
    "sqlite_viewer": "app/routers/sqlite_viewer.py",
    "record_explorer": "app/routers/record_explorer.py",
}

SHELL_TARGETS = {
    "legacy_shell_backup": "scripts/backup.sh",
    "replication_wrapper": "scripts/replicate_backups.sh",
}

DIRECT_DB_CALLS = {
    "sqlite3.connect",
    "engine.connect",
    "engine.begin",
    "food.engine.connect",
    "food.engine.begin",
}

STORAGE_NAMES = {
    "DB_PATH",
    "DB_URL",
    "DATA_DIR",
    "BACKUP_DIR",
    "UPLOAD_DIR",
    "TRACKER_BACKUP_DIR",
    "TRACKER_DATA_DIR",
}

FILESYSTEM_CALLS = {
    "open",
    "mkdir",
    "unlink",
    "replace",
    "rename",
    "rmdir",
    "write_text",
    "write_bytes",
    "read_bytes",
    "copy2",
    "copyfile",
    "copytree",
    "rmtree",
    "extractall",
}


def dotted(node):
    if isinstance(node, ast.Name):
        return node.id

    if isinstance(node, ast.Attribute):
        prefix = dotted(node.value)
        return prefix + "." + node.attr if prefix else node.attr

    return ""


def source_function_names(tree):
    return sorted(
        node.name
        for node in tree.body
        if isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef)
        )
    )


def scan_python(relative):
    path = ROOT / relative
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))

    operations = []
    direct_db = []
    global_storage = []
    filesystem = []
    dependencies = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = dotted(node.func)
            short = name.rsplit(".", 1)[-1]

            if name in DIRECT_DB_CALLS:
                direct_db.append({
                    "line": node.lineno,
                    "call": name,
                })

            if short in FILESYSTEM_CALLS:
                filesystem.append({
                    "line": node.lineno,
                    "call": name,
                })

            if name == "Depends" and node.args:
                dependencies.append(
                    dotted(node.args[0])
                )

            if short in (
                "create_backup",
                "prune_backups",
                "verify_backup",
                "verify_restorable",
                "restore_status",
                "replicate",
            ):
                operations.append({
                    "line": node.lineno,
                    "call": name,
                })

        elif isinstance(node, ast.Attribute):
            if node.attr in STORAGE_NAMES:
                global_storage.append({
                    "line": node.lineno,
                    "name": dotted(node),
                })

    executable = any(
        isinstance(node, ast.If)
        and any(
            isinstance(child, ast.Compare)
            and isinstance(child.left, ast.Name)
            and child.left.id == "__name__"
            for child in ast.walk(node.test)
        )
        for node in tree.body
    )

    return {
        "path": relative,
        "functions": source_function_names(tree),
        "executable_main": executable,
        "direct_database_calls": sorted(
            direct_db,
            key=lambda item: item["line"],
        ),
        "global_storage_references": sorted(
            global_storage,
            key=lambda item: item["line"],
        ),
        "filesystem_candidates": sorted(
            filesystem,
            key=lambda item: item["line"],
        ),
        "backup_operations": sorted(
            operations,
            key=lambda item: item["line"],
        ),
        "declared_dependencies": sorted(set(dependencies)),
    }


def router_dependencies(relative):
    tree = ast.parse(
        (ROOT / relative).read_text(),
        filename=relative,
    )

    names = []

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue

        if not any(
            isinstance(target, ast.Name)
            and target.id == "router"
            for target in node.targets
        ):
            continue

        call = node.value

        if (
            not isinstance(call, ast.Call)
            or dotted(call.func) != "APIRouter"
        ):
            continue

        for keyword in call.keywords:
            if keyword.arg != "dependencies":
                continue

            if not isinstance(
                keyword.value, (ast.List, ast.Tuple)
            ):
                continue

            for element in keyword.value.elts:
                if not isinstance(element, ast.Call):
                    continue

                if dotted(element.func) != "Depends":
                    continue

                if element.args:
                    names.append(dotted(element.args[0]))

    return sorted(set(names))


def build_report():
    python = {
        key: scan_python(path)
        for key, path in PYTHON_TARGETS.items()
    }

    shell = {}

    for key, relative in SHELL_TARGETS.items():
        content = (ROOT / relative).read_text()

        shell[key] = {
            "path": relative,
            "uses_tracker_data_dir": (
                "TRACKER_DATA_DIR" in content
            ),
            "calls_sqlite3_cli": (
                "sqlite3 " in content
            ),
            "calls_archive_cli": (
                "tar " in content
            ),
            "executes_python": (
                ".venv/bin/python" in content
            ),
        }

    browser_guards = {
        "backups": {
            "path": PYTHON_TARGETS["backup_router"],
            "required": "require_backup_storage397",
        },
        "maintenance_review": {
            "path": PYTHON_TARGETS["maintenance_router"],
            "required": "require_direct_storage397",
        },
        "sqlite_viewer": {
            "path": PYTHON_TARGETS["sqlite_viewer"],
            "required": "require_direct_storage397",
        },
        "record_explorer": {
            "path": PYTHON_TARGETS["record_explorer"],
            "required": "require_direct_storage397",
        },
    }

    for item in browser_guards.values():
        item["declared"] = (
            item["required"] in router_dependencies(
                item["path"]
            )
        )

    global_defaults = [
        "app/backup.py: create_backup defaults to config.DATA_DIR",
        "app/backup.py: backup archives default to BACKUP_DIR",
        "scripts/tracker_backup.py: scheduled create uses defaults",
        "scripts/tracker_replica.py: replication uses configured roots",
        "scripts/backup.sh: legacy shell backup uses TRACKER_DATA_DIR",
    ]

    return {
        "release": "409",
        "status": "migration-in-progress",
        "multi_user_enabled": False,
        "application_isolation_complete": False,
        "background_job_isolation_complete": False,
        "scope": "source-only; no background processes executed",
        "python_targets": python,
        "shell_targets": shell,
        "browser_guards": browser_guards,
        "global_default_review": global_defaults,
        "next_actions": [
            "Define explicit storage context for background jobs",
            "Separate administrator whole-instance backup policy",
            "Verify background backup and restore account boundaries",
            "Audit legacy shell backup scheduling and necessity",
            "Add isolated cross-account backup integration tests",
            "Retain secondary-account denial until all gates pass",
        ],
    }


def validate(report):
    for key, item in report["browser_guards"].items():
        if not item["declared"]:
            raise RuntimeError(
                "Missing browser storage guard: " + key
            )

    for key in (
        "backup_entrypoint",
        "replication_entrypoint",
        "maintenance_entrypoint",
    ):
        if not report["python_targets"][key]["executable_main"]:
            raise RuntimeError(
                "Missing expected executable entry point: "
                + key
            )

    backup = report["python_targets"]["backup_library"]
    if "create_backup" not in backup["functions"]:
        raise RuntimeError("Backup creation routine missing")

    if not backup["direct_database_calls"]:
        raise RuntimeError(
            "Direct backup SQLite calls were not detected"
        )

    if not report["shell_targets"][
        "legacy_shell_backup"
    ]["calls_sqlite3_cli"]:
        raise RuntimeError(
            "Legacy shell SQLite backup not detected"
        )

    if (
        report["multi_user_enabled"]
        or report["application_isolation_complete"]
        or report["background_job_isolation_complete"]
    ):
        raise RuntimeError(
            "Unexpected completed-isolation assertion"
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the complete read-only inventory as JSON",
    )

    args = parser.parse_args()

    report = build_report()
    validate(report)

    if args.json:
        print(json.dumps(report, indent=2))
        return

    print("=== RELEASE 409 BACKGROUND STORAGE AUDIT ===")

    for key, item in report["browser_guards"].items():
        print(
            "PASS: Guarded browser route:",
            key,
            "->",
            item["required"],
        )

    print()
    print("Background source inventory:")

    for key, item in report["python_targets"].items():
        print(
            f"{key}: "
            f"database={len(item['direct_database_calls'])}, "
            f"filesystem={len(item['filesystem_candidates'])}, "
            f"storage_paths={len(item['global_storage_references'])}, "
            f"entrypoint={item['executable_main']}"
        )

    print()
    print("Shell backup inventory:")

    for key, item in report["shell_targets"].items():
        print(
            f"{key}: "
            f"sqlite3_cli={item['calls_sqlite3_cli']}, "
            f"python_wrapper={item['executes_python']}"
        )

    print()
    print("MULTI-USER ISOLATION: INCOMPLETE")
    print("BACKGROUND-JOB ISOLATION: INCOMPLETE")
    print("ADDITIONAL ACCOUNTS: DISABLED")
    print("EXISTING BACKUP OPERATIONS: UNCHANGED")
    print("PASS: Release 409 read-only audit")


if __name__ == "__main__":
    try:
        main()
    except (
        OSError,
        SyntaxError,
        ValueError,
        RuntimeError,
    ) as error:
        print("ERROR:", error, file=sys.stderr)
        raise SystemExit(1)
