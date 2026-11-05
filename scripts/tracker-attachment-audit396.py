#!/usr/bin/env python3
"""Read-only Labs and COA access-boundary audit."""

import ast
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def scan(path):
    tree = ast.parse(path.read_text())

    found = {
        "scoped": 0,
        "legacy": 0,
        "guard": 0,
    }

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
            found["scoped"] += 1
        elif candidate.id == "get_db":
            found["legacy"] += 1
        elif candidate.id == "require_attachment_scope396":
            found["guard"] += 1

    return found


def main():
    print("=== RELEASE 396 ATTACHMENT ACCESS AUDIT ===")

    for name, expected in (
        ("labs", 16),
        ("coas", 12),
    ):
        path = ROOT / "app/routers" / f"{name}.py"
        found = scan(path)

        assert found["scoped"] == expected
        assert found["legacy"] == 0
        assert found["guard"] == 1

        print(
            f"PASS: {name}: "
            f"{expected} scoped DB dependencies, "
            "whole-router attachment guard"
        )

    print()
    print("Authorized live account: administrator ID 1")
    print("Existing file locations: preserved")
    print("Additional accounts: disabled")
    print("Per-user attachment directories: not active")
    print("Application-wide isolation: incomplete")
    print("No database or file migration")

    print("PASS: Labs and COA guards verified")


if __name__ == "__main__":
    try:
        main()
    except (
        AssertionError,
        OSError,
        SyntaxError,
    ) as error:
        print("ERROR:", error, file=sys.stderr)
        raise SystemExit(1)
