#!/usr/bin/env python3
"""Offline, read-only prioritization of three conservative CSRF inventories.

Priority means *review order*, never vulnerability severity or proof of
effective CSRF protection. No application import, network call or data access.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.tracker_csrf_route_inventory620 import inventory as route_inventory
from scripts.tracker_csrf_form_crosswalk621 import crosswalk as form_crosswalk
from scripts.tracker_csrf_js_inventory622 import report as js_report

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def prioritized_report(root: Path) -> dict:
    declared = route_inventory(root)
    html = form_crosswalk(root)
    js = js_report(root)
    findings = []

    for entry in html["controls"]:
        unresolved = not entry["candidate_handlers"]
        # A dynamic destination is difficult to resolve by static analysis,
        # and a native form needs explicit token/browser review.
        is_dynamic = entry["path_class"] != "literal-path"
        priority = "P1" if unresolved or is_dynamic else "P2"
        findings.append({
            "priority": priority,
            "category": "template-write-control",
            "file": entry["template"],
            "line": entry["line"],
            "method": entry["method"],
            "route_hint": entry["path"],
            "evidence": {
                "control_kind": entry["kind"],
                "path_class": entry["path_class"],
                "candidate_handlers": entry["candidate_handlers"],
            },
            "review_reason": (
                "Unresolved or dynamic template destination"
                if priority == "P1"
                else "Static destination matched a declared handler; verify real CSRF behavior"
            ),
            "review_status": "MANUAL_REVIEW_REQUIRED",
        })

    for entry in js["candidates"]:
        # UNKNOWN means method or route determination needs source review.
        unknown = entry["method_hint"] == "UNKNOWN"
        findings.append({
            "priority": "P1" if unknown else "P2",
            "category": "javascript-request-site",
            "file": entry["file"],
            "line": entry["line"],
            "method": entry["method_hint"],
            "route_hint": None,
            "evidence": {"call_kind": entry["kind"]},
            "review_reason": (
                "Unknown request method; inspect JavaScript and runtime request"
                if unknown else
                "Potential literal unsafe request; inspect token and origin handling"
            ),
            "review_status": "MANUAL_REVIEW_REQUIRED",
        })

    # Absence from the scanned template crosswalk cannot demonstrate a
    # missing user interface, because JS/runtime/mounted routes are incomplete.
    # Label these P3 so unresolved evidence receives attention first.
    candidate_keys = {
        (h["file"], h["line"])
        for row in html["controls"] for h in row["candidate_handlers"]
    }
    for route in declared:
        if (route["file"], route["line"]) in candidate_keys:
            continue
        findings.append({
            "priority": "P3",
            "category": "declared-route-without-static-template-match",
            "file": route["file"],
            "line": route["line"],
            "method": ",".join(route["methods"]),
            "route_hint": route["route"],
            "evidence": {"handler": route["handler"]},
            "review_reason": (
                "No literal template match in static scan; route may be "
                "driven by JS, external client, dynamic forms or mounted paths"
            ),
            "review_status": "MANUAL_REVIEW_REQUIRED",
        })

    order = {"P1": 0, "P2": 1, "P3": 2}
    findings.sort(key=lambda r: (
        order[r["priority"]], r["category"], r["file"], r["line"],
        r["method"], r["route_hint"] or "",
    ))
    counts = {level: sum(f["priority"] == level for f in findings)
              for level in ("P1", "P2", "P3")}
    return {
        "schema_version": 1,
        "scope": "offline static-source review queue; incomplete by design",
        "runtime_csrf_verification": False,
        "vulnerability_assessment": False,
        "priority_meaning": {
            "P1": "Unresolved or dynamic evidence: inspect first",
            "P2": "Static candidate with identifiable write method: verify next",
            "P3": "Declared handler without a static template match: reconcile",
        },
        "totals": {
            "unsafe_handler_declarations": len(declared),
            "template_write_controls": len(html["controls"]),
            "javascript_request_candidates": len(js["candidates"]),
            "review_items": len(findings),
            "by_priority": counts,
        },
        "findings": findings,
        "limitations": [
            "Review priority is not risk/severity and is not proof of vulnerability.",
            "Matches never establish signed CSRF protection; require runtime HTTP/HTTPS evidence.",
            "Route and template scans omit dynamic registration, prefixes, middleware and mounted apps.",
            "JS text scan can miss wrappers and multiline methods or include false positives.",
            "Never enable global strict CSRF based only on this report.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--limit", type=int, default=0,
                        help="Show first N prioritized findings; default all")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    if not (root / "app" / "templates").is_dir():
        parser.error("App template source directory not found")
    if args.limit < 0:
        parser.error("--limit must be nonnegative")
    data = prioritized_report(root)
    if args.limit:
        data["findings"] = data["findings"][:args.limit]
        data["shown_items"] = len(data["findings"])
    print(json.dumps(data, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
