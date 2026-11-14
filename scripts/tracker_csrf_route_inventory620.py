#!/usr/bin/env python3
"""Read-only source inventory of declared unsafe Tracker HTTP routes.

This is a conservative review aid, NOT proof of effective runtime CSRF coverage:
dynamic registrations, mounted applications, aliases and middleware behavior
must also be reviewed manually. No request is sent or database accessed.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

UNSAFE = frozenset({"POST", "PUT", "PATCH", "DELETE"})
ROOT = Path(__file__).resolve().parents[1]


def literal(node):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, RecursionError):
        return None


def extract(path: Path, root: Path) -> list[dict]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    rows = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            target = decorator.func
            if not isinstance(target, ast.Attribute):
                continue
            method = target.attr.upper()
            if method in UNSAFE:
                methods = [method]
            elif method == "API_ROUTE":
                kw = next((x.value for x in decorator.keywords if x.arg == "methods"), None)
                values = literal(kw) if kw is not None else None
                if not isinstance(values, (tuple, list, set)):
                    continue
                methods = sorted(UNSAFE & {str(v).upper() for v in values})
            else:
                continue
            if not methods:
                continue
            route = literal(decorator.args[0]) if decorator.args else None
            if not isinstance(route, str):
                route = "<dynamic>"
            code = ast.get_source_segment(path.read_text(encoding="utf-8"), node) or ""
            rows.append({
                "file": str(path.relative_to(root)),
                "line": node.lineno,
                "handler": node.name,
                "route": route,
                "methods": methods,
                "has_request_parameter": any(arg.arg == "request" for arg in node.args.args),
                "mentions_csrf": "csrf" in code.lower(),
                "review_status": "MANUAL_REVIEW_REQUIRED",
            })
    return rows


def inventory(root: Path) -> list[dict]:
    files = sorted((root / "app").rglob("*.py"))
    rows = [r for path in files for r in extract(path, root)]
    return sorted(rows, key=lambda r: (r["file"], r["line"], r["route"]))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if not (root / "app").is_dir():
        parser.error("App source directory not found")
    rows = inventory(root)
    print(json.dumps({
        "schema_version": 1,
        "scope": "static route declarations only",
        "runtime_csrf_verification": False,
        "total_handlers": len(rows),
        "routes": rows,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
