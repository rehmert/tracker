#!/usr/bin/env python3
"""Release 578: immutable source-to-route CSRF review ledger, NOT clearance.

Combines tracked unsafe route declarations, HTML/HTMX write sites, and the
Release 576 JavaScript triage. Matches only literal path/method pairs or
literal path-pattern shapes; dynamic and indirect requests stay unresolved.
Never executes application code, reads a database, or makes network requests.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNSAFE = frozenset({"POST", "PUT", "PATCH", "DELETE"})
PATH_PARAMETER = re.compile(r"\{[A-Za-z_][A-Za-z_0-9]*(?::[^{}]+)?\}")


def load_script(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Missing source scanner: {path.name}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def path_shape(path: str) -> str | None:
    """Normalize FastAPI literal dynamic segments; never infer expression URLs."""
    if not isinstance(path, str) or not path.startswith("/") or "?" in path:
        return None
    if any(x in path for x in ("{{", "{%", "${", "`", "+", "*", "\\", "..")):
        return None
    if re.search(r"[<>\s]", path):
        return None
    return PATH_PARAMETER.sub("{}", path).rstrip("/") or "/"


def route_pattern(path: str) -> re.Pattern | None:
    shape = path_shape(path)
    if shape is None:
        return None
    # Don't match literal path like /foo against a dynamic /foo/{id}.
    segments = path.strip("/").split("/")
    parts = []
    for seg in segments:
        if PATH_PARAMETER.fullmatch(seg):
            parts.append(r"[^/{}$?#]+")
        elif PATH_PARAMETER.search(seg):
            return None
        else:
            parts.append(re.escape(seg))
    return re.compile("^/" + "/".join(parts) + "/?$")


def literal_route_candidates(path: str, routes: list[dict]) -> list[dict]:
    # A literal JS string may contain query parameters. Only full literal
    # paths are candidates; placeholders, concatenation and templates are not.
    if path_shape(path) is None or PATH_PARAMETER.search(path):
        return []
    matches = []
    for route in routes:
        pattern = route_pattern(route["path"])
        if pattern is not None and pattern.fullmatch(path):
            matches.append(route)
    return matches


def build(root: Path = ROOT) -> dict:
    root = Path(root).resolve()
    scanner = load_script(root / "scripts/tracker-csrf-readiness.py",
                          "csrf578_readiness")
    js = load_script(root / "scripts/tracker_csrf_js_triage576.py",
                     "csrf578_js")
    inventory = scanner.build(root)
    triage = js.build(root)
    routes = inventory["routes"]
    if len(routes) != inventory["summary"]["unsafe_route_declarations"]:
        raise ValueError("Route inventory incomplete")
    if len(triage["callsites"]) != inventory["summary"]["javascript_request_callsites"]:
        raise ValueError("JS inventory and triage disagree")
    if len({(r["method"], r["path"], r["file"], r["line"]) for r in routes}) != len(routes):
        raise ValueError("Duplicate route records")
    route_keys = {(r["method"], r["path"], r["file"], r["line"]) for r in routes}

    js_rows = []
    mappings = defaultdict(list)
    for row in triage["callsites"]:
        path = row["callsite_line_path"]
        method = row["callsite_line_method"]
        # Never treat a nearby literal, or implicit GET, as a method match.
        candidates = literal_route_candidates(path, routes) if path else []
        paired = [r for r in candidates if r["method"] == method] if method in UNSAFE else []
        status = ("literal_path_and_unsafe_method_source_hint"
                  if paired else "unresolved_dynamic_or_unpaired_request")
        mapped = [dict(r) for r in paired]
        for r in paired:
            mappings[(r["method"], r["path"], r["file"], r["line"])].append(
                {"file": row["file"], "line": row["line"], "kind": row["kind"]}
            )
        js_rows.append({
            **row, "route_source_candidates": mapped,
            "route_attribution": status,
            "runtime_executed": False,
            "csrf_compatible": None,
        })

    native = []
    for record in inventory["html_and_htmx"]:
        method = (record.get("method") or "").upper()
        action = record.get("action", record.get("target", ""))
        # Native forms with omitted action submit to their rendered URL.
        # Treat this as unresolved, even when a same-file route looks likely.
        candidates = literal_route_candidates(action, routes) if action else []
        matched = [r for r in candidates if r["method"] == method] if method in UNSAFE else []
        native.append({
            **record, "route_source_candidates": matched,
            "route_attribution": ("literal_action_and_unsafe_method_source_hint"
                                  if matched else "unresolved_dynamic_or_implicit_action"),
            "runtime_executed": False,
            "csrf_compatible": None,
        })

    route_rows = []
    for route in routes:
        key = (route["method"], route["path"], route["file"], route["line"])
        assert key in route_keys
        hints = mappings.get(key, [])
        route_rows.append({
            **route, "javascript_source_hints": hints,
            "runtime_qualified": False,
            "strict_csrf_compatible": None,
        })

    counts = Counter(row["route_attribution"] for row in js_rows)
    # Explicit, source-addressed human review queue. It is not a
    # demonstration that an unsafe route is reachable in a browser.
    review_queue = [
        {
            "priority": "dynamic_or_unpaired_js",
            "file": row["file"], "line": row["line"],
            "kind": row["kind"], "method_hint": row["callsite_line_method"],
            "path_hint": row["callsite_line_path"],
        }
        for row in js_rows
        if row["route_attribution"] == "unresolved_dynamic_or_unpaired_request"
    ]
    review_queue += [
        {
            "priority": "implicit_or_dynamic_native",
            "file": row["file"], "line": row["line"],
            "kind": row["kind"], "method_hint": row.get("method"),
            "path_hint": row.get("action", row.get("target", "")),
        }
        for row in native
        if row["route_attribution"] == "unresolved_dynamic_or_implicit_action"
    ]
    review_queue.sort(key=lambda row: (
        row["priority"], row["file"], row["line"], row["kind"]
    ))
    return {
        "status": "source_only_not_strict_csrf_clearance",
        "summary": {
            "unsafe_routes": len(route_rows),
            "javascript_callsites": len(js_rows),
            "native_or_htmx_sites": len(native),
            "js_literal_source_pair_hints": counts["literal_path_and_unsafe_method_source_hint"],
            "js_unresolved": counts["unresolved_dynamic_or_unpaired_request"],
            "runtime_qualified_routes": 0,
            "js_runtime_verified": 0,
            "pending_manual_review": len(review_queue),
        },
        "limitations": [
            "Syntactically paired path/method remains a source hint, not executed request evidence",
            "A dynamic fetch method or URL can target ANY unsafe route",
            "Implicit form action and template interpolation require rendered browser review",
            "No runtime clearance is inferred from unrelated existing browser tests",
            "No live DEV or PROD strict-CSRF policy changes",
        ],
        "routes": route_rows,
        "javascript": js_rows,
        "native": native,
        "review_queue": review_queue,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    report = build()
    print("CSRF_578_LEDGER=SOURCE_ONLY_NOT_CLEARANCE")
    for key, value in report["summary"].items():
        print(f"{key.upper()}={value}")
    if args.json is not None:
        dest = args.json
        if (dest.parent.parent != Path("/tmp")
                or not re.fullmatch(r"tracker-csrf578\.[A-Za-z0-9_]{8,}", dest.parent.name)
                or not dest.parent.is_dir() or dest.parent.is_symlink()
                or dest.exists() or dest.is_symlink()):
            parser.error("JSON export requires a fresh /tmp/tracker-csrf578.*/ file")
        with dest.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, sort_keys=True)
            handle.write("\n")
        dest.chmod(0o600)
        print(f"REPORT={dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
