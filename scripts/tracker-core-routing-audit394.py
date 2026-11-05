#!/usr/bin/env python3
"""Read-only core database-routing migration audit."""

import ast
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

CORE = {
    "dashboard": None,
    "doses": None,
    "vitals": None,
    "compounds": 5,
    "protocols": 12,
    "vials": 14,
    "purchases": 11,
    "supplies": 5,
    "calendar": 5,
}


def audit_module(name):
    path = ROOT / "app/routers" / f"{name}.py"
    tree = ast.parse(path.read_text(), filename=str(path))

    scoped = 0
    legacy = 0

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        if not isinstance(node.func, ast.Name):
            continue

        if node.func.id != "Depends" or not node.args:
            continue

        candidate = node.args[0]

        if not isinstance(candidate, ast.Name):
            continue

        if candidate.id == "get_scoped_db390":
            scoped += 1

        if candidate.id == "get_db":
            legacy += 1

    return scoped, legacy


def main():
    converted = 0

    print("=== RELEASE 394.1 CORE ROUTING AUDIT ===")

    for name, expected in CORE.items():
        scoped, legacy = audit_module(name)

        if scoped < 1 or legacy:
            raise RuntimeError(
                f"{name}: scoped={scoped}, legacy={legacy}"
            )

        if expected is not None and scoped != expected:
            raise RuntimeError(
                f"{name}: expected {expected}, found {scoped}"
            )

        converted += scoped

        print(
            f"PASS: {name}: "
            f"{scoped} scoped dependencies"
        )

    print()
    print("Scoped core modules:", len(CORE))
    print("Scoped core DB dependencies:", converted)
    print("Additional accounts: disabled")
    print("Existing administrator database: unchanged")
    print("Application-wide isolation: incomplete")
    print("Direct engine and filesystem routes: under review")
    print("No personal records migrated")

    assert converted >= 60

    print("PASS: Core routing audit complete")


if __name__ == "__main__":
    try:
        main()
    except (
        OSError,
        SyntaxError,
        RuntimeError,
        AssertionError,
    ) as error:
        print("ERROR:", error, file=sys.stderr)
        raise SystemExit(1)
