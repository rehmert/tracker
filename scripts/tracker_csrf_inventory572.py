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
import re
from urllib.parse import urlsplit
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
    """Walk actual FastAPI 0.162 included-router contexts, preserving scopes.

    This FastAPI version stores included APIRouters lazily as _IncludedRouter,
    rather than copying every APIRoute into app.routes. The library's
    effective_candidates() returns resolved _EffectiveRouteContext objects
    with inherited dependencies, full paths and HTTP methods. Never infer
    that a wrapper with no .methods has no unsafe child endpoints.
    """
    found = []

    def scan(routes, prefix="", mounted=False):
        for route in routes:
            if type(route).__name__ == "_IncludedRouter":
                expand = getattr(route, "effective_candidates", None)
                if not callable(expand):
                    raise ValueError("FastAPI included-router expansion unavailable")
                candidates = expand()
                if not isinstance(candidates, list):
                    raise ValueError("FastAPI included-router expansion changed")
                scan(candidates, prefix=prefix, mounted=mounted)
                continue

            original = getattr(route, "original_route", route)
            effective = route if original is not route else None

            if isinstance(original, Mount):
                mount = getattr(effective, "starlette_route", None) or original
                mount_path = getattr(mount, "path", None)
                if not isinstance(mount_path, str):
                    raise ValueError("Mounted route has no effective path")
                if hasattr(original.app, "routes"):
                    scan(original.app.routes,
                         prefix=prefix + mount_path.rstrip("/"),
                         mounted=True)
                continue

            if effective is not None and not isinstance(original, APIRoute):
                # A context representing a plain Starlette Route can be unsafe;
                # reject it instead of claiming complete FastAPI coverage.
                methods = {
                    str(method).upper()
                    for method in (getattr(route, "methods", None)
                                   or getattr(original, "methods", None) or ())
                } & UNSAFE
                if methods:
                    raise ValueError(
                        "Unsafe effective non-FastAPI route cannot be classified: "
                        + type(original).__name__
                    )
                continue

            methods = {
                str(method).upper()
                for method in (getattr(route, "methods", None) or ())
            } & UNSAFE
            if not methods:
                continue
            if not isinstance(original, APIRoute) or not hasattr(route, "dependant"):
                raise ValueError(
                    f"Unsafe non-FastAPI route cannot be classified: "
                    f"{type(original).__name__} {getattr(original, 'path', '?')}"
                )

            path = getattr(route, "path", None)
            if not isinstance(path, str) or not path.startswith("/"):
                raise ValueError("Unsafe route has no resolved absolute path")

            deps = dependency_calls(route)
            source = inspect.getsourcefile(original.endpoint) or ""
            try:
                source = str(Path(source).resolve().relative_to(ROOT))
            except ValueError:
                source = "outside-tracked-source"
            for method in sorted(methods):
                full_path = prefix + path
                has_auth = any(d.endswith(".require_auth") for d in deps)
                has_multipart = any(
                    d.endswith(".enforce_multipart_csrf520") for d in deps
                )
                report = {
                    "method": method,
                    "path": full_path,
                    "file": source,
                    "line": getattr(original.endpoint, "__code__", None).co_firstlineno
                    if hasattr(original.endpoint, "__code__") else None,
                    "mounted": mounted,
                    "global_auth_dependency": has_auth,
                    "global_multipart_dependency": has_multipart,
                    "signed_session_exception": method == "POST"
                    and full_path in SESSION,
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
        classes = sorted({type(route).__name__ for route in routes})
        raise ValueError(
            "No registered unsafe routes discovered; refusing empty report: "
            + ", ".join(classes)
        )
    return sorted(found, key=lambda item: (
        item["path"], item["method"], item["file"],
    ))


def static_inventory(root: Path) -> dict:
    source = root / "scripts/tracker-csrf-readiness.py"
    spec = importlib.util.spec_from_file_location("csrf_readiness572", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build(root)



# Only a whole Jinja path segment whose last attribute is an ID is
# shape-matchable. Never evaluate template code or interpolate values.
_JINJA_ID_SEGMENT574 = re.compile(
    r"\{\{\s*[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*\."
    r"(?:id|[A-Za-z_]\w*_id)\s*\}\}\Z"
)
_ROUTE_PARAM_SEGMENT574 = re.compile(r"\{[^{}]+\}\Z")


def _templated_route_shape574(method: str, target: str, writes: list[dict]) -> bool:
    """Heuristically pair template-only ID segments to route parameters.

    A match means the route *shape* exists; NOT that Jinja rendered the
    correct ID or that CSRF/header submission succeeds in a browser.
    """
    if not target.startswith("/") or target.startswith("//") or "{%" in target:
        return False
    parsed = urlsplit(target)
    # A dynamic query or fragment may alter submission semantics, even
    # when the path segment resembles a registered route. Review manually.
    if any(marker in value for value in (parsed.query, parsed.fragment)
           for marker in ("{{", "{%")):
        return False
    path = parsed.path
    segments = path.split("/")
    if not any(_JINJA_ID_SEGMENT574.fullmatch(seg) for seg in segments):
        return False
    for route in writes:
        if route["mounted"] or route["method"] != method:
            continue
        route_segments = route["path"].split("/")
        if len(route_segments) != len(segments):
            continue
        matched = True
        for actual, expected in zip(segments, route_segments):
            if _JINJA_ID_SEGMENT574.fullmatch(actual):
                if not _ROUTE_PARAM_SEGMENT574.fullmatch(expected):
                    matched = False
                    break
            elif actual != expected:
                matched = False
                break
        if matched:
            return True
    return False


def classify_browser_entrypoints(static: dict, writes: list[dict]) -> list[dict]:
    """Match literal static form/HTMX actions against effective write routes.

    This is triage, NOT executable-browser proof. Dynamic template actions,
    external URLs, empty actions and unrelated HTMX targets remain manual.
    """
    patterns = []
    for row in writes:
        if row["mounted"]:
            continue
        candidate = re.sub(r"\{[^{}]+\}", "__ROUTE_PARAM__", row["path"])
        pattern = re.escape(candidate).replace("__ROUTE_PARAM__", r"[^/]+")
        patterns.append((row["method"], re.compile(r"\A" + pattern + r"\Z")))

    findings = []
    for entry in static["html_and_htmx"]:
        method = entry.get("method", "").upper()
        target = (entry.get("action", "") if entry["kind"] == "html_form"
                  else entry.get("target", "")) or ""
        if method not in UNSAFE or not target or method == "DYNAMIC":
            category = "manual_dynamic_or_implicit"
        elif target.startswith(("http://", "https://", "//")):
            category = "manual_absolute_or_external"
        elif not target.startswith("/"):
            category = "manual_relative_or_fragment"
        elif "{{" in target or "{%" in target:
            category = (
                "templated_route_shape_matched"
                if _templated_route_shape574(method, target, writes)
                else "manual_dynamic_or_implicit"
            )
        else:
            path = urlsplit(target).path
            category = (
                "literal_route_matched"
                if any(m == method and rx.fullmatch(path) for m, rx in patterns)
                else "literal_route_not_matched"
            )
        findings.append({
            "kind": entry["kind"],
            "file": entry["file"],
            "line": entry["line"],
            "method": method,
            "target": target,
            "classification": category,
        })
    return findings

def build(application, root: Path = ROOT) -> dict:
    writes = registered_writes(application)
    static = static_inventory(root)
    browser_entries = classify_browser_entrypoints(static, writes)
    browser_status = Counter(x["classification"] for x in browser_entries)
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
            "literal_browser_write_routes_matched": browser_status["literal_route_matched"],
            "literal_browser_write_routes_unmatched": browser_status["literal_route_not_matched"],
            "templated_route_shapes_matched": browser_status["templated_route_shape_matched"],
            "browser_targets_unresolved_without_shape_match": sum(
                count for status, count in browser_status.items()
                if status.startswith("manual_")
            ),
            # A source-shape match still requires real rendered browser QA;
            # do not reduce the outstanding compatibility review count.
            "browser_writes_needing_manual_resolution": sum(
                count for status, count in browser_status.items()
                if status.startswith("manual_")
                or status == "templated_route_shape_matched"
            ),
        },
        "global_dependency_gaps": missing_dependency,
        "runtime_not_in_static_scanner": unlisted_runtime,
        "static_not_registered_in_this_configuration": not_registered,
        "file_upload_writes": sorted(upload_writes),
        "browser_entrypoint_triage": browser_entries,
        "javascript_request_callsites": static["javascript"],
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
            "Templated ID segment shape matching does not verify rendered URLs or CSRF",
            "Static browser action-to-route matching is heuristic, not token validation",
            "Dynamic JS, template inheritance and mounted app routing require manual review",
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
