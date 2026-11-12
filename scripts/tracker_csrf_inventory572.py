#!/usr/bin/env python3
"""Inventory live registered unsafe routes and CSRF coverage evidence, read-only.

Uses a disposable, caller-specified TRACKER_DATA_DIR and imports the
application WITHOUT running the FastAPI lifespan or making HTTP requests.
The inventory is NOT a claim that every write route is CSRF-secure.
"""
from __future__ import annotations

import argparse
import importlib.util
import inspect
import json
import os
from pathlib import Path
from collections import Counter

from fastapi.routing import APIRoute
from starlette.routing import Mount

ROOT = Path(__file__).resolve().parents[1]
UNSAFE = frozenset({"POST", "PUT", "PATCH", "DELETE"})
SESSION = frozenset({
    "/login", "/logout", "/account/password",
    "/account/sessions/revoke-others", "/account/users", "/account/users/edit",
})
KNOWN_STRICT_BROWSER_EXAMPLES = frozenset({
    "/compounds", "/coas/new", "/pages/preview", "/vitals",
    "/pk/compounds", "/labs/import-csv",
})


def name(callable_obj) -> str:
    return (getattr(callable_obj, "__module__", "")
            + "." + getattr(callable_obj, "__qualname__", str(callable_obj)))


def dependency_calls(route: APIRoute) -> set[str]:
    """Flatten declared FastAPI dependencies; not a proof of auth behavior."""
    result: set[str] = set()
    pending = list(route.dependant.dependencies)
    while pending:
        dependency = pending.pop()
        result.add(name(dependency.call))
        pending.extend(dependency.dependencies)
    return result


def registered_writes(application) -> list[dict]:
    """Include real APIRoutes in nested mounted FastAPI applications."""
    found = []

    def scan(routes, prefix="", mounted=False):
        for route in routes:
            if isinstance(route, Mount) and hasattr(route.app, "routes"):
                scan(route.app.routes, prefix + route.path.rstrip("/"), True)
            else:
                # Inspect registered routes by actual methods, not only one
                # FastAPI route class. Never silently omit unsafe methods.
                methods = {
                    str(method).upper()
                    for method in (getattr(route, "methods", None) or ())
                } & UNSAFE
                if not methods:
                    continue
                if not hasattr(route, "dependant"):
                    raise ValueError(
                        f"Unsafe non-FastAPI route cannot be classified: "
                        f"{type(route).__name__} {getattr(route, 'path', '?')}"
                    )
                deps = dependency_calls(route)
                source = inspect.getsourcefile(route.endpoint) or ""
                try:
                    source = str(Path(source).resolve().relative_to(ROOT))
                except ValueError:
                    source = "outside-tracked-source"
                for method in sorted(methods):
                    path = prefix + route.path
                    has_auth = any(d.endswith(".require_auth") for d in deps)
                    has_multipart = any(
                        d.endswith(".enforce_multipart_csrf520") for d in deps
                    )
                    report = {
                        "method": method,
                        "path": path,
                        "file": source,
                        "line": getattr(route.endpoint, "__code__", None).co_firstlineno
                        if hasattr(route.endpoint, "__code__") else None,
                        "mounted": mounted,
                        "global_auth_dependency": has_auth,
                        "global_multipart_dependency": has_multipart,
                        "signed_session_exception": method == "POST"
                        and path in SESSION,
                        "body_fields": [
                            {"name": p.name,
                             "type": type(p.field_info).__name__}
                            for p in route.dependant.body_params
                        ],
                        "needs_manual_endpoint_review": True,
                    }
                    found.append(report)

    routes = list(application.routes)
    if not routes:
        raise ValueError("FastAPI application registered no routes")
    scan(routes)
    if not found:
        classes = sorted({type(r).__name__ for r in routes})
        raise ValueError(
            "No registered unsafe routes discovered; refusing empty report: "
            + ", ".join(classes)
        )
    return sorted(found, key=lambda x: (x["path"], x["method"], x["file"]))


def static_inventory(root: Path) -> dict:
    source = root / "scripts/tracker-csrf-readiness.py"
    spec = importlib.util.spec_from_file_location("csrf_readiness572", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build(root)


def build(application, root: Path = ROOT) -> dict:
    writes = registered_writes(application)
    static = static_inventory(root)
    static_keys = {(r["method"], r["path"]) for r in static["routes"]}
    runtime_keys = {(r["method"], r["path"]) for r in writes}
    unlisted_runtime = sorted(runtime_keys - static_keys)
    not_registered = sorted(static_keys - runtime_keys)
    missing_dependency = sorted(
        (r["method"], r["path"])
        for r in writes if not r["mounted"] and
        (not r["global_auth_dependency"]
         or not r["global_multipart_dependency"])
    )
    upload_writes = [
        (r["method"], r["path"]) for r in writes
        if any(f["type"] == "File" for f in r["body_fields"])
    ]
    counts = Counter(r["method"] for r in writes)
    return {
        "status": "inventory_only_manual_review_required",
        "source_commit": None,  # Filled only by caller when independently pinned.
        "summary": {
            "registered_unsafe_routes": len(writes),
            "methods": dict(sorted(counts.items())),
            "static_declared_routes": len(static["routes"]),
            "runtime_missing_from_static_scanner": len(unlisted_runtime),
            "static_missing_from_runtime_registration": len(not_registered),
            "root_routes_missing_global_dependencies": len(missing_dependency),
            "registered_mounted_write_routes": sum(r["mounted"] for r in writes),
            "file_upload_writes_detected": len(upload_writes),
            "html_htmx_write_sites": len(static["html_and_htmx"]),
            "js_request_callsites": len(static["javascript"]),
        },
        "global_dependency_gaps": missing_dependency,
        "runtime_not_in_static_scanner": unlisted_runtime,
        "static_not_registered_in_this_configuration": not_registered,
        "file_upload_writes": sorted(upload_writes),
        "strict_browser_example_paths": sorted(
            p for p in KNOWN_STRICT_BROWSER_EXAMPLES
            if any(r["path"] == p for r in writes)
        ),
        "limitations": [
            "Registered routes reflect THIS isolated configuration; optional mounts may be absent",
            "Global dependencies are structural evidence, not verification of endpoint behavior",
            "Mounted subapps require separate middleware and token review",
            "Static scanner misses dynamic routes and non-router files; differences must be triaged",
            "Browser examples are not a complete coverage matrix",
            "Every unsafe endpoint still requires auth, proxy-origin and CSRF behavior review",
            "No installed DEV/PROD policy change is authorized by this inventory",
        ],
        "routes": writes,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, help="Optional output file in /tmp")
    args = parser.parse_args(argv)
    data_dir = os.environ.get("TRACKER_DATA_DIR", "")
    data = Path(data_dir)
    sandbox = data.parent
    if not (
        data.is_absolute()
        and data.name == "data"
        and sandbox.parent == Path("/tmp")
        and sandbox.name.startswith("tracker-csrf572.")
        and data.is_dir() and not data.is_symlink()
        and sandbox.is_dir() and not sandbox.is_symlink()
    ):
        parser.error("TRACKER_DATA_DIR must be /tmp/tracker-csrf572.*/data")
    if args.json is not None and (
        args.json.parent != sandbox or args.json.exists()
        or args.json.is_symlink()
    ):
        parser.error("--json destination must be a new file inside the sandbox")
    # Importing app.main does not run startup lifespan. No server is started.
    from app.main import app
    report = build(app)
    print("CSRF_INVENTORY=READ_ONLY")
    for key, value in report["summary"].items():
        print(f"{key.upper()}={value}")
    if report["global_dependency_gaps"]:
        print("STRUCTURAL_GLOBAL_DEPENDENCY_GAPS=REVIEW_REQUIRED")
    else:
        print("STRUCTURAL_GLOBAL_DEPENDENCY_GAPS=NONE_ON_ROOT_APP")
    print("UNREGISTERED_OR_UNSCANNED_ROUTES=MANUAL_REVIEW_REQUIRED")
    print("STRICT_CSRF_ROLLOUT=NOT_AUTHORIZED")
    if args.json:
        with args.json.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
            handle.write("\n")
        print(f"INVENTORY_JSON={args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
