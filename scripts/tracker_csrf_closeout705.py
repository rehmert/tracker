#!/usr/bin/env python3
"""Release 705: conservative read-only CSRF closeout inventory.

Source matches are not evidence of successful signed browser writes.
This tool never enables strict CSRF or certifies complete route coverage.
"""
from __future__ import annotations

import argparse
import json
import sys

from scripts.tracker_csrf_reconcile627 import build


def summarize(report: dict) -> dict:
    unmapped = int(report["remaining_without_positive_source_witness"])
    manual = int(report["manual_review_items_unchanged"])
    session = int(report["session_account_routes_not_certified"])
    if min(unmapped, manual, session) < 0:
        raise ValueError("Invalid source-evidence count")
    return {
        "schema_version": 1,
        "source_only": True,
        "unsafe_routes_in_frozen_source_inventory": report["current_unsafe_routes"],
        "unmapped_positive_browser_routes": unmapped,
        "manual_review_items": manual,
        "session_account_routes_without_independent_clearance": session,
        "new_source_mapped_routes_not_runtime_certified": len([
            row for row in report["new_627_positive_routes"]
            if not row["full_dev_runtime_qualified"]
        ]),
        "newer_routes_outside_frozen_inventory_may_exist": True,
        "global_enforcement_authorized": False,
        "decision": "BLOCKED_PRESERVE_REPORT_ONLY",
        "top_unmapped_workstreams": report["remaining_route_workstreams"][:12],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--require-complete", action="store_true",
                        help="Fail rather than infer runtime security clearance")
    args = parser.parse_args(argv)
    try:
        result = summarize(build())
    except (OSError, ValueError, KeyError, TypeError, AssertionError) as exc:
        print(f"CSRF_705_INVENTORY=ERROR ({type(exc).__name__})",
              file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("CSRF_705_UNMAPPED_POSITIVE=" +
              str(result["unmapped_positive_browser_routes"]))
        print("CSRF_705_MANUAL_REVIEW=" + str(result["manual_review_items"]))
        print("CSRF_705_SESSION_REVIEW=" +
              str(result["session_account_routes_without_independent_clearance"]))
        print("CSRF_705_GLOBAL_ENFORCEMENT=BLOCKED")
    if args.require_complete:
        # No static-only inventory can establish runtime evidence, even if
        # a future source report says every mapped route has a witness.
        print("CSRF_705_CLOSEOUT=BLOCKED_PENDING_RUNTIME_AND_MANUAL_EVIDENCE")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
