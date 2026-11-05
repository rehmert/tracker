#!/usr/bin/env python3
"""Read-only source inventory of database access patterns.

This is a triage report, not a proof of exhaustive isolation.
It does not inspect or modify personal records.
"""

import ast
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"


def inspect_file(path):
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))

    found = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "sqlite3":
                    found.add("sqlite3 import")

        elif isinstance(node, ast.ImportFrom):
            if node.module == "db":
                names = {a.name for a in node.names}

                if "engine" in names:
                    found.add("direct global engine")

                if "SessionLocal" in names:
                    found.add("direct SessionLocal")

                if "get_db" in names:
                    found.add("legacy get_db")

            if node.module == "scoped_db390":
                found.add("scoped DB dependency")

            if node.module == "user_db389":
                found.add("user DB dependency")

        elif isinstance(node, ast.Attribute):
            if (
                isinstance(node.value, ast.Name)
                and node.value.id == "config"
                and node.attr in (
                    "DB_PATH",
                    "DB_URL",
                    "DATA_DIR",
                    "UPLOAD_DIR",
                    "LAB_DIR",
                )
            ):
                found.add("process-wide data path")

    # FastAPI dependency usage is checked separately from
    # import statements to avoid treating an unused import
    # as completed conversion.
    if "Depends(get_scoped_db390)" in source:
        found.add("scoped dependency used")

    if "Depends(get_db)" in source:
        found.add("legacy dependency used")

    return found


def main():
    print("=== RELEASE 390 DATA ACCESS INVENTORY ===")
    print("Source root:", APP)
    print()

    direct = []
    scoped = []
    legacy = []

    for path in sorted(APP.rglob("*.py")):
        relative = path.relative_to(ROOT).as_posix()
        patterns = inspect_file(path)

        if not patterns:
            continue

        if "scoped dependency used" in patterns:
            scoped.append(relative)

        if "legacy dependency used" in patterns:
            legacy.append(relative)

        if patterns.intersection({
            "direct global engine",
            "direct SessionLocal",
            "sqlite3 import",
            "process-wide data path",
        }):
            direct.append((relative, patterns))

    print("Scoped FastAPI dependency modules:")
    for name in scoped:
        print("  ", name)

    print()
    print("Legacy dependency modules:", len(legacy))
    print("Direct access / global path candidates:", len(direct))

    print()
    print("Priority review candidates:")

    priority = (
        "app/routers/food.py",
        "app/routers/labs.py",
        "app/routers/coas.py",
        "app/routers/backups.py",
        "app/routers/sqlite_viewer.py",
        "app/backup.py",
    )

    for name in priority:
        path = ROOT / name
        if not path.exists():
            continue

        patterns = inspect_file(path)
        print(
            "  ",
            name,
            ":",
            ", ".join(sorted(patterns)) or "no flagged pattern",
        )

    print()
    print("STATUS")
    print("Additional user accounts: disabled")
    print("Global engine: unchanged")
    print("Per-user filesystem routing: not active")
    print("Completed multi-user isolation: NO")
    print("Audit is read-only and heuristic.")

    if not all(
        "Depends(get_scoped_db390)"
        in (ROOT / name).read_text()
        for name in (
            "app/routers/dashboard.py",
            "app/routers/doses.py",
            "app/routers/vitals.py",
        )
    ):
        raise RuntimeError(
            "Required Release 390 conversions missing"
        )


if __name__ == "__main__":
    try:
        main()
    except (
        OSError,
        SyntaxError,
        RuntimeError,
    ) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
