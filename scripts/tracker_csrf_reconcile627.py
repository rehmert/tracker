#!/usr/bin/env python3
"""Conservative Release 627 positive-route reconciliation (source only).

Never claims global enforcement readiness, and never invents runtime evidence.
Only the 19 remaining routes explicitly exercised by the three 627 signed
lifecycle modules may be moved to an observed-in-targeted-run bucket.
All other unsafe routes keep their original source/manual review status.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from scripts.tracker_csrf_gap_plan590 import build as baseline

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/tracker-browser-qualify.sh"

# These are explicit signed write + negative forgery pairs with persisted state
# checks. The route is a normalized FastAPI declaration, not a URL guess.
WITNESSES = {
    "tests/browser/test_csrf_signed_lifecycles627.py": (
        ("POST", "/protocols"),
        ("POST", "/protocols/{pid}/active"),
        ("POST", "/protocols/{pid}/delete"),
        ("POST", "/pages"),
        ("POST", "/pages/{pid}"),
        ("POST", "/pages/{pid}/delete"),
        ("POST", "/labs"),
        ("POST", "/labs/{rid}/results"),
        ("POST", "/labs/{rid}/delete"),
    ),
    "tests/browser/test_csrf_purchase_children627.py": (
        ("POST", "/purchases/{pid}/bac-water"),
        ("POST", "/purchases/{pid}/delete"),
        ("POST", "/purchases/{pid}/supplies"),
        ("POST", "/purchases/{pid}/supplies/{sid}/delete"),
        ("POST", "/purchases/{pid}/supplies/{sid}/edit"),
        ("POST", "/purchases/{pid}/vials"),
        ("POST", "/purchases/{pid}/vials/{vid}/delete"),
    ),
    "tests/browser/test_csrf_coa_lifecycle627.py": (
        ("POST", "/coas/{cid}/delete"),
        ("POST", "/coas/{cid}/edit"),
        ("POST", "/coas/{cid}/verify"),
    ),
}

# Route-declaration paths require explicit reference to their dynamic test
# request shapes or validated creation, not a meaningless substring check.
MODULE_MARKERS = {
    "tests/browser/test_csrf_signed_lifecycles627.py": (
        '("protocols", "/protocols", "/protocols")',
        '("pages", "/pages/new", "/pages")',
        '("labs", "/labs/new", "/labs")',
        'created_path + "/active"',
        'created_path + "/delete"',
        'created_path + "/results"',
        'next_path = created_path',
        'SELECT title,body FROM pages',
        'SELECT analyte,value,unit FROM lab_results',
    ),
    "tests/browser/test_csrf_purchase_children627.py": (
        'write("/purchases",',
        'write(supply_path,',
        'f"/purchases/{pid}/bac-water"',
        'f"/purchases/{pid}/supplies/{sid}/edit"',
        'f"/purchases/{pid}/supplies/{sid}/delete"',
        'f"/purchases/{pid}/vials"',
        'f"/purchases/{pid}/vials/{vial[0]}/delete"',
        'f"/purchases/{pid}/delete"',
        'SELECT id,purchased_qty FROM supplies',
    ),
    "tests/browser/test_csrf_coa_lifecycle627.py": (
        'form.get_by_role("button", name="Create COA").click()',
        'signed(route + "/edit",',
        'signed(route + "/verify",',
        'signed(route + "/delete",',
        '"QA627 verified" in verified.text()',
    ),
}


def build() -> dict:
    report = baseline()
    remaining = {(r["method"], r["path"]) for r in report["unqualified_routes"]}
    known = {(r["method"], r["path"]) for r in report["candidate_routes"]}
    runner = RUNNER.read_text()
    start = runner.index('echo "=== STRICT CSRF CORE TESTS PASSED ==="')
    end = runner.index('if [[ "$MODE" == targeted && "$TARGETED_MODULE" == csrf-batch627 ]]')
    full_section = runner[start:end]

    mapped = {}
    for module, routes in WITNESSES.items():
        src = (ROOT / module).read_text()
        if src.count("max_redirects=0") < 2 or "status == 403" not in src:
            raise ValueError("Missing forgery/signed write assertions: " + module)
        if "form=" not in src and module != "tests/browser/test_csrf_signed_lifecycles627.py":
            raise ValueError("No form-encoded signed submission: " + module)
        for marker in MODULE_MARKERS[module]:
            if marker not in src:
                raise ValueError("Positive source marker missing " + module + ": " + marker)
        if full_section.count(module) != 1:
            raise ValueError("Positive witness not exactly once in full gate: " + module)
        for key in routes:
            if key in mapped:
                raise ValueError("Duplicate positive route: " + str(key))
            mapped[key] = module

    if len(mapped) != 19 or not set(mapped) <= remaining or set(mapped) & known:
        raise ValueError("Release 627 source witnesses differ from baseline gap")
    if report["total_unsafe_routes"] != 144 or len(known) != 83 or len(remaining) != 61:
        raise ValueError("Baseline unsafe-route inventory changed; manual reassessment required")

    uncovered = [
        {"method": method, "path": path, "workstream": path.strip("/").split("/")[0]}
        for method, path in sorted(remaining - mapped.keys())
    ]
    count = Counter(row["workstream"] for row in uncovered)
    return {
        "status": "BLOCKED_PENDING_FULL_DEV_AND_MANUAL_REVIEW",
        "source_only": True,
        "global_enforcement_authorized": False,
        "full_dev_qualification_observed_by_this_report": False,
        "original_unsafe_routes": 144,
        "pre_627_candidate_routes": 83,
        "pre_627_unqualified_routes": 61,
        "new_627_targeted_positive_route_witnesses": len(mapped),
        "new_627_positive_routes": [
            {"method": method, "path": path, "test_module": module,
             "full_dev_runtime_qualified": False}
            for (method, path), module in sorted(mapped.items())
        ],
        "remaining_without_positive_route_witness": len(uncovered),
        "remaining_route_workstreams": [
            {"workstream": group, "routes": number}
            for group, number in sorted(count.items(), key=lambda row: (-row[1], row[0]))
        ],
        "remaining_routes": uncovered,
        "manual_review_items_unchanged": report["manual_review_queue_size"],
        "session_account_routes_not_certified": 6,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = build()
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("CSRF_627_STATUS=" + result["status"])
        print("CSRF_627_TARGETED_POSITIVE_ROUTES=" +
              str(result["new_627_targeted_positive_route_witnesses"]))
        print("CSRF_627_STILL_WITHOUT_POSITIVE_WITNESS=" +
              str(result["remaining_without_positive_route_witness"]))
        print("CSRF_627_MANUAL_REVIEW_UNCHANGED=" +
              str(result["manual_review_items_unchanged"]))
        print("CSRF_627_GLOBAL_ENFORCEMENT=BLOCKED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
