#!/usr/bin/env python3
"""Release 576: source-only CSRF JavaScript and route review (NOT clearance).

Resolves each fetch/htmx.ajax call expression rather than borrowing nearby
method literals. A URL expression, Request object, variable options, and
anything the lightweight parser cannot prove remain explicitly unresolved.
No network, installed credentials, database, or application runtime is used.
"""
from __future__ import annotations

import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CALL = re.compile(r"\b(?:fetch|htmx\.ajax)\s*\(")
METHOD = re.compile(
    r"""\bmethod\s*:\s*(?P<quote>['"])(?P<method>GET|POST|PUT|PATCH|DELETE)(?P=quote)""",
    re.I,
)
LITERAL = re.compile(r"""\A(?P<quote>['"])(?P<url>/[^'"]*)(?P=quote)\Z""")
UNSAFE = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Existing or newly added isolated tests, never a claim of passing results.
# Do not mark a route as tested because its shape resembles a different route.
BROWSER_TESTS_DEFINED = {
    ("POST", "/vials/{vid}/reconstitute"):
        "tests/browser/test_strict_csrf576.py::test_576_real_preparation_correction_signed_and_forged",
    ("POST", "/vials/{vid}/preparations/{eid}/edit"):
        "tests/browser/test_strict_csrf576.py::test_576_real_preparation_correction_signed_and_forged",
    ("POST", "/vials/bulk/validate-selection"):
        "tests/browser/test_strict_csrf576.py::test_576_bulk_preview_fetch_and_origin_fail_closed",
    ("POST", "/vials/bulk/delete-preview"):
        "tests/browser/test_strict_csrf576.py::test_576_bulk_preview_fetch_and_origin_fail_closed",
    ("POST", "/compounds"):
        "tests/browser/test_strict_csrf521.py::test_521_native_urlencoded_compound_create_and_reject_forgery",
    ("POST", "/coas/new"):
        "tests/browser/test_strict_csrf521.py::test_521_native_coa_multipart_upload_and_signed_verification",
    ("POST", "/pages/preview"):
        "tests/browser/test_strict_csrf521.py::test_521_htmx_preview_writes_include_signed_header",
    ("POST", "/vitals"):
        "tests/browser/test_strict_csrf521.py::test_521_htmx_delete_vitals_needs_token_and_preserves_other_records",
    ("POST", "/pk/compounds"):
        "tests/browser/test_strict_csrf521.py::test_521_same_origin_fetch_auto_header_and_missing_header_denial",
    ("POST", "/food/water"):
        "tests/browser/test_strict_csrf521.py::test_575_mobile_quick_entry_signed_fetch_and_implicit_forms",
}


def _source_module(path: Path):
    spec = importlib.util.spec_from_file_location(
        "tracker_csrf_js_review575_for576", path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Tracked Release 575 scanner missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read_parens(source: str, opening: int) -> str | None:
    """Return the text inside a balanced call or None if lexically uncertain."""
    if source[opening:opening + 1] != "(":
        return None
    depth = 1
    quote = None
    escaped = False
    line_comment = False
    block_comment = False
    for index in range(opening + 1, min(len(source), opening + 8192)):
        ch = source[index]
        nxt = source[index + 1] if index + 1 < len(source) else ""
        if line_comment:
            if ch == "\n":
                line_comment = False
            continue
        if block_comment:
            if ch == "*" and nxt == "/":
                block_comment = False
            continue
        if quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
            continue
        if ch in ("'", '"', "`"):
            quote = ch
        elif ch == "/" and nxt == "/":
            line_comment = True
        elif ch == "/" and nxt == "*":
            block_comment = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return source[opening + 1:index]
    return None


def _arguments(expression: str) -> list[str]:
    """Split at top-level commas, retaining nested object and array values."""
    parts = []
    start = 0
    depth = []
    quote = None
    escaped = False
    for index, ch in enumerate(expression):
        if quote:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                quote = None
            continue
        if ch in ("'", '"', "`"):
            quote = ch
        elif ch in "([{":
            depth.append(ch)
        elif ch in ")]}":
            if not depth:
                return []
            expected = {")": "(", "]": "[", "}": "{"}[ch]
            if depth.pop() != expected:
                return []
        elif ch == "," and not depth:
            parts.append(expression[start:index].strip())
            start = index + 1
    if quote or depth:
        return []
    parts.append(expression[start:].strip())
    return parts


def analyze_callsite(row: dict, root: Path = ROOT) -> dict:
    path = (root / row["file"]).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Callsite path escaped source root")
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines(keepends=True)
    number = row["line"]
    if not isinstance(number, int) or not 1 <= number <= len(lines):
        raise ValueError("Callsite line invalid")
    match = CALL.search(lines[number - 1])
    if match is None:
        raise ValueError("Prior scanner callsite no longer exists")

    opening = sum(map(len, lines[:number - 1])) + match.end() - 1
    expression = _read_parens(source, opening)
    args = _arguments(expression) if expression is not None else []
    kind = row["kind"]
    target = None
    method = None

    if not args:
        category = "unresolved_expression"
    else:
        first = args[0]
        if kind == "htmx_ajax_callsite":
            # htmx.ajax(method, path, ...), not the fetch(url, options) API.
            method_match = re.fullmatch(r"""['"](GET|POST|PUT|PATCH|DELETE)['"]""", first, re.I)
            if method_match:
                method = method_match.group(1).upper()
                category = ("htmx_explicit_unsafe" if method in UNSAFE
                            else "htmx_explicit_get")
            else:
                category = "htmx_dynamic_method"
            if len(args) > 1:
                literal = LITERAL.fullmatch(args[1])
                target = literal.group("url") if literal else None
        else:
            literal = LITERAL.fullmatch(first)
            target = literal.group("url") if literal else None
            options = args[1] if len(args) > 1 else ""
            explicit = METHOD.search(options) if options.startswith("{") else None
            if explicit:
                method = explicit.group("method").upper()
                category = ("explicit_unsafe" if method in UNSAFE
                            else "explicit_get")
            elif options.startswith("{") and re.search(r"\bmethod\s*:", options):
                category = "dynamic_method"
            elif (len(args) == 1 or options.startswith("{")) and first[:1] in ("'", '"'):
                method = "GET"
                category = "implicit_get_url_expression"
            else:
                # Input can be Request with an unsafe method, or options can
                # be constructed outside the call. Never claim implicit GET.
                category = "request_or_options_unresolved"

    return {
        "file": row["file"],
        "line": number,
        "kind": kind,
        "release575_hint": row["classification"],
        "method_source_class": category,
        "literal_method": method,
        "exact_literal_target": target,
        "runtime_compatibility_verified": False,
    }


def build(root: Path = ROOT) -> dict:
    root = Path(root)
    review = _source_module(root / "scripts/tracker_csrf_js_review575.py")
    old = review.build(root)
    rows = [analyze_callsite(item, root) for item in old["callsites"]]
    classes = dict(sorted(Counter(
        r["method_source_class"] for r in rows
    ).items()))
    source = review.source_inventory(root)
    routes = []
    for route in source["routes"]:
        key = (route["method"], route["path"])
        links = [
            {"file": r["file"], "line": r["line"]}
            for r in rows
            if r["literal_method"] == key[0]
            and r["exact_literal_target"] == key[1]
        ]
        routes.append({
            "method": key[0],
            "path": key[1],
            "source": route["file"],
            "line": route["line"],
            "exact_js_source_matches": links,
            "browser_test_defined": BROWSER_TESTS_DEFINED.get(key),
            "browser_test_run_verified": False,
            "manual_verification_outstanding": True,
        })
    return {
        "status": "SOURCE_REVIEW_ONLY_STRICT_ENFORCEMENT_NOT_AUTHORIZED",
        "summary": {
            "js_request_callsites": len(rows),
            "js_method_source_classes": classes,
            "explicit_unsafe_source_callsites": sum(
                r["method_source_class"] in ("explicit_unsafe", "htmx_explicit_unsafe")
                for r in rows
            ),
            "other_or_unresolved_source_callsites": sum(
                r["method_source_class"] not in ("explicit_unsafe", "htmx_explicit_unsafe")
                for r in rows
            ),
            "static_unsafe_route_declarations": len(routes),
            "routes_with_test_definitions": sum(
                x["browser_test_defined"] is not None for x in routes
            ),
        },
        "limitations": [
            "This audit does not execute JavaScript, network requests, or tests",
            "The route list is from static declarations, not the complete effective runtime router",
            "JS target expressions, Request inputs and external options remain unresolved",
            "POST preview operations remain unsafe HTTP methods despite read-only business logic",
            "Existing test definitions are not proof of a passing current candidate",
            "Mounted secondary-account routes and all 144 registered write routes require a separate runtime report",
            "Neither installed DEV nor PROD strict-CSRF enforcement may be enabled from this report",
        ],
        "javascript": rows,
        "static_routes": routes,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args(argv)
    result = build()
    print("CSRF_576_REVIEW=SOURCE_ONLY")
    for name, value in result["summary"].items():
        print(f"{name.upper()}={value}")
    print("STRICT_CSRF_ROLLOUT_AUTHORIZED=NO")
    if args.json is not None:
        dest = args.json
        if (dest.parent.parent != Path("/tmp")
                or not dest.parent.name.startswith("tracker-csrf576.")
                or not dest.parent.is_dir()
                or dest.parent.is_symlink()
                or dest.exists() or dest.is_symlink()):
            parser.error("--json requires a new file in /tmp/tracker-csrf576.*/")
        with dest.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
        dest.chmod(0o600)
        print(f"CSRF_576_JSON={dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
