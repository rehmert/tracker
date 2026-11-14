#!/usr/bin/env python3
"""Offline crosswalk of unsafe route declarations and HTML/HTMX write controls.

This produces *review candidates*, not a CSRF verdict. It does not execute
Jinja, import the application, send requests, or inspect private data.
Dynamic attributes and JavaScript-generated controls require manual review.
"""
from __future__ import annotations

import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from scripts.tracker_csrf_route_inventory620 import inventory

ROOT = Path(__file__).resolve().parents[1]
UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}
HTMX = {"hx-post": "POST", "hx-put": "PUT", "hx-patch": "PATCH", "hx-delete": "DELETE"}
PARAM = re.compile(r"\{[^{}]+\}")


class WriteControls(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.controls = []
        self.form_stack = []
        self.line = 0

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        line = self.getpos()[0]
        if tag == "form":
            method = (values.get("method") or "get").upper()
            action = values.get("action") or "<implicit-current-url>"
            self.form_stack.append({"method": method, "action": action, "line": line})
            if method in UNSAFE:
                self.controls.append({"line": line, "tag": tag, "method": method, "path": action,
                                      "kind": "native-form"})
        for attr, method in HTMX.items():
            if attr in values:
                self.controls.append({"line": line, "tag": tag, "method": method,
                                      "path": values[attr] or "<dynamic>",
                                      "kind": "htmx"})

    def handle_endtag(self, tag):
        if tag == "form" and self.form_stack:
            self.form_stack.pop()


def controls(root: Path) -> list[dict]:
    rows = []
    for path in sorted((root / "app" / "templates").rglob("*.html")):
        parser = WriteControls()
        parser.feed(path.read_text(encoding="utf-8"))
        for item in parser.controls:
            rows.append({"template": str(path.relative_to(root)), **item})
    return rows


def clean_path(raw: str) -> str | None:
    if not raw or not raw.startswith("/") or "{{" in raw or "{%" in raw:
        return None
    parsed = urlsplit(raw)
    return parsed.path if parsed.path.startswith("/") else None


def route_pattern(route: str):
    if not route.startswith("/") or route == "<dynamic>":
        return None
    pieces = []
    for piece in route.strip("/").split("/"):
        if piece.startswith("{") and piece.endswith("}"):
            pieces.append(r"[^/]+")
        else:
            pieces.append(re.escape(piece))
    return re.compile(r"^/" + "/".join(pieces) + r"/?$")


def crosswalk(root: Path) -> dict:
    routes = inventory(root)
    writes = controls(root)
    for item in writes:
        path = clean_path(item["path"])
        item["path_class"] = "literal-path" if path else "dynamic-or-relative"
        item["candidate_handlers"] = []
        if path:
            for r in routes:
                if item["method"] in r["methods"]:
                    pattern = route_pattern(r["route"])
                    if pattern is not None and pattern.fullmatch(path):
                        item["candidate_handlers"].append({
                            "file": r["file"], "line": r["line"], "handler": r["handler"],
                        })
        item["review_status"] = "MANUAL_REVIEW_REQUIRED"
    return {
        "schema_version": 1,
        "scope": "static HTML/Jinja attributes and Python route decorators",
        "runtime_csrf_verification": False,
        "total_declared_unsafe_handlers": len(routes),
        "total_visible_template_write_controls": len(writes),
        "unmatched_or_dynamic_controls": sum(
            not item["candidate_handlers"] for item in writes
        ),
        "controls": writes,
        "review_notes": [
            "Unmatched does not imply vulnerable; JavaScript, forms with implicit action and router prefixes may require separate review.",
            "Matched does not imply CSRF-safe; middleware, auth, signed tokens and browser tests must be checked independently.",
            "HTMLParser does not execute Jinja; conditionals, includes and generated controls can change runtime behavior.",
            "JavaScript-generated requests, dynamically registered routes and mounted sub-applications are outside this inventory.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if not (root / "app" / "templates").is_dir():
        parser.error("Template directory not found")
    print(json.dumps(crosswalk(root), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
