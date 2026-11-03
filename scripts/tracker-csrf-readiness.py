#!/usr/bin/env python3
"""Source-only inventory of Tracker browser write mechanisms.

This is NOT a security certification or CSRF enforcement.
It locates static source evidence to plan token coverage.
No application database, credentials, or network access.
"""

import argparse
import importlib.util
import json
import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}
HTMX = ("hx-post", "hx-put", "hx-patch", "hx-delete")


class FormScanner(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms = []
        self.htmx = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        line = self.getpos()[0]

        if tag == "form":
            method = attributes.get("method", "get")
            if "{{" in method or "{%" in method:
                method = "dynamic"
            self.forms.append({
                "line": line,
                "method": method.lower(),
                "action": attributes.get("action", ""),
            })

        for key in HTMX:
            if key in attributes:
                self.htmx.append({
                    "line": line,
                    "method": key[3:].upper(),
                    "target": attributes[key],
                    "tag": tag,
                })


def route_inventory(root):
    path = root / "scripts/tracker-route-audit.py"
    spec = importlib.util.spec_from_file_location(
        "tracker_csrf_route_source", path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return [
        record
        for record in module.analyze()
        if record["method"] in UNSAFE
    ]


def template_inventory(root):
    records = []
    for path in sorted((root / "app/templates").rglob("*.html")):
        scanner = FormScanner()
        scanner.feed(path.read_text(encoding="utf-8"))
        relative = path.relative_to(root).as_posix()

        for form in scanner.forms:
            if form["method"] in ("post", "dynamic"):
                records.append({
                    "kind": "html_form",
                    "file": relative,
                    **form,
                })

        for request in scanner.htmx:
            records.append({
                "kind": "htmx",
                "file": relative,
                **request,
            })

    return records


def javascript_inventory(root):
    records = []
    files = sorted((root / "app/static").rglob("*.js"))
    # Inline script sections in templates may also issue fetch.
    files += sorted((root / "app/templates").rglob("*.html"))

    for path in files:
        source = path.read_text(encoding="utf-8")
        relative = path.relative_to(root).as_posix()

        for number, line in enumerate(source.splitlines(), 1):
            if re.search(r"\bfetch\s*\(", line):
                records.append({
                    "kind": "fetch_callsite",
                    "file": relative,
                    "line": number,
                    "detail": (
                        "Fetch callsite, including potentially "
                        "dynamic method; manual review required"
                    ),
                })

            if re.search(
                r"\bhtmx\.ajax\s*\(", line
            ):
                records.append({
                    "kind": "htmx_ajax_callsite",
                    "file": relative,
                    "line": number,
                    "detail": "Programmatic HTMX call",
                })

    return records


def build(root=ROOT):
    root = Path(root)
    routes = route_inventory(root)
    forms = template_inventory(root)
    scripts = javascript_inventory(root)

    return {
        "status": "inventory_only_not_csrf_protected",
        "scope": "tracked-style application source",
        "limitations": [
            "Dynamic JavaScript methods require manual inspection",
            "Rendered or dynamically generated forms may be missed",
            "Client-side source matches do not prove executable paths",
            "No CSRF token coverage or server-side validation is verified",
        ],
        "summary": {
            "unsafe_route_declarations": len(routes),
            "html_and_htmx_write_sites": len(forms),
            "javascript_request_callsites": len(scripts),
        },
        "routes": routes,
        "html_and_htmx": forms,
        "javascript": scripts,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json", type=Path,
        help="Write complete source inventory as JSON",
    )
    args = parser.parse_args()

    report = build()

    print("=== TRACKER CSRF READINESS ===")
    print("Status: AUDIT ONLY; tokens NOT enforced")

    for name, count in report["summary"].items():
        print(f"{name}: {count}")

    print()
    print("=== WRITE ROUTES BY SOURCE MODULE ===")

    groups = {}
    for record in report["routes"]:
        groups[record["file"]] = (
            groups.get(record["file"], 0) + 1
        )

    for path, count in sorted(
        groups.items(), key=lambda item: (-item[1], item[0])
    ):
        print(f"{count:4}  {path}")

    print()
    print("=== BROWSER WRITE ENTRY POINTS ===")

    for record in report["html_and_htmx"]:
        print(
            record["kind"],
            f'{record["file"]}:{record["line"]}',
            record.get("method", ""),
            record.get("action", record.get("target", "")),
        )

    print()
    print("=== JAVASCRIPT REQUEST CALLSITES ===")

    for record in report["javascript"]:
        print(
            f'{record["file"]}:{record["line"]}',
            record["kind"],
        )

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(report, indent=2) + "\n",
            encoding="utf-8",
        )
        print("JSON report:", args.json)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
