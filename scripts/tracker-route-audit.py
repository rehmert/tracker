#!/usr/bin/env python3
"""Read-only AST audit of literal FastAPI routes."""

import ast
import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTERS = ROOT / "app" / "routers"


def literal_string(node):
    if isinstance(node, ast.Constant) and isinstance(
        node.value, str
    ):
        return node.value
    return None


def analyze():
    routes = []
    for path in sorted(ROUTERS.glob("*.py")):
        tree = ast.parse(
            path.read_text(encoding="utf-8"),
            filename=str(path),
        )

        prefixes = {}

        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue

            if not isinstance(node.value, ast.Call):
                continue

            constructor = node.value.func

            if not (
                isinstance(constructor, ast.Name)
                and constructor.id == "APIRouter"
            ):
                continue

            prefix = ""
            for keyword in node.value.keywords:
                if keyword.arg == "prefix":
                    prefix = literal_string(keyword.value)
                    if prefix is None:
                        raise ValueError(
                            f"Dynamic router prefix: {path}"
                        )

            for target in node.targets:
                if isinstance(target, ast.Name):
                    prefixes[target.id] = prefix

        for node in tree.body:
            if not isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef),
            ):
                continue

            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue

                target = decorator.func
                if not isinstance(target, ast.Attribute):
                    continue

                if target.attr not in (
                    "get", "post", "put", "patch", "delete"
                ):
                    continue

                if not isinstance(
                    target.value, ast.Name
                ):
                    continue

                router_name = target.value.id
                if router_name not in prefixes:
                    continue

                if not decorator.args:
                    continue

                route_path = literal_string(
                    decorator.args[0]
                )
                if route_path is None:
                    raise ValueError(
                        f"Dynamic route path: {path}:{node.lineno}"
                    )

                full_path = (
                    prefixes[router_name] + route_path
                )

                routes.append({
                    "method": target.attr.upper(),
                    "path": full_path,
                    "file": str(path.relative_to(ROOT)),
                    "line": node.lineno,
                })

    return routes


def main():
    routes = analyze()
    grouped = collections.defaultdict(list)

    for route in routes:
        key = route["method"], route["path"]
        grouped[key].append(route)

    duplicates = {
        key: entries
        for key, entries in grouped.items()
        if len(entries) > 1
    }

    print(
        f"Audited {len(routes)} "
        "literal FastAPI route declarations."
    )

    for key, entries in sorted(duplicates.items()):
        print("DUPLICATE:", *key)
        for entry in entries:
            print(
                " ",
                entry["file"],
                "line",
                entry["line"],
            )

    if duplicates:
        raise SystemExit(1)

    print("PASS: No duplicate effective route paths")


if __name__ == "__main__":
    main()
