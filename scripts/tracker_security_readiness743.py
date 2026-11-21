#!/usr/bin/env python3
"""Release 743 read-only current-source unsafe-route and CSRF clearance gate.

The historical 627/705 ledgers are frozen; new application routes must not
vanish from review just because those earlier totals were stable.
No requests, DB access, credential reads, or policy changes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from scripts.tracker_csrf_route_inventory620 import inventory
from scripts.tracker_csrf_reconcile627 import WITNESSES

ROOT = Path(__file__).resolve().parents[1]
UNSAFE = frozenset(("POST", "PUT", "PATCH", "DELETE"))
# Explicit newly added mutations. None is presumed to have complete strict
# positive+negative HTTP/HTTPS evidence because a page displays a signed form.
NEW_MACD = frozenset({
    ("POST", "/supplies/{sid}/edit"),
    ("POST", "/supplies/{sid}/delete"),
    ("POST", "/supplies/categories/{cid}/edit"),
    ("POST", "/supplies/categories/{cid}/delete"),
    ("POST", "/workouts/equipment/{equipment_id}/edit"),
    ("POST", "/workouts/equipment/{equipment_id}/delete"),
    ("POST", "/workouts/routines/{routine_id}/rename"),
    ("POST", "/workouts/routines/{routine_id}/delete"),
    ("POST", "/food/saved/{product_id}/delete"),
})
WITNESS_CANDIDATES = frozenset(
    (method, path)
    for rows in WITNESSES.values()
    for method, path in rows
)


def route_rows(root: Path) -> list[dict]:
    result = []
    for row in inventory(root):
        for method in row["methods"]:
            if method in UNSAFE:
                result.append({
                    "method": method, "path": row["route"],
                    "file": row["file"], "line": row["line"],
                })
    return sorted(result, key=lambda x: (
        x["method"], x["path"], x["file"], x["line"]
    ))


def build(root: Path = ROOT) -> dict:
    if not (root / "app").is_dir():
        raise ValueError("Application source unavailable")
    source = (root / "app" / "main.py").read_text(encoding="utf-8")
    policy = (root / "app" / "csrf_policy289.py").read_text(encoding="utf-8")
    if ('os.environ.get("TRACKER_CSRF_ENFORCE", "0")' not in source
            or "if setting != '1':" not in policy):
        raise ValueError("Report-only default or strict gate source changed")

    routes = route_rows(root)
    keys = {(r["method"], r["path"]) for r in routes}
    missing_macd = NEW_MACD - keys
    if missing_macd:
        raise ValueError("Expected MACD unsafe route declarations changed")

    documented = keys & WITNESS_CANDIDATES
    not_in_frozen_witnesses = keys - WITNESS_CANDIDATES
    dynamic = [x for x in routes if x["path"] == "<dynamic>"]
    # An explicit source witness is NOT proof that a route ran correctly
    # with strict CSRF in both browsers or was independently reviewed.
    return {
        "schema": 1,
        "scope": "static source declarations only",
        "total_unsafe_declarations": len(routes),
        "unique_unsafe_routes": len(keys),
        "dynamic_unsafe_declarations": len(dynamic),
        "historical_candidate_source_witnesses_still_declared": len(documented),
        "routes_outside_frozen_candidate_source_witnesses": len(not_in_frozen_witnesses),
        "unreviewed_recent_macd_routes": [
            {"method": method, "path": path}
            for method, path in sorted(NEW_MACD)
        ],
        "newer_routes_evidence_not_assumed": True,
        "strict_http_https_runtime_qualified": False,
        "multipart_stream_compatibility_certified": False,
        "session_account_manual_review_complete": False,
        "global_strict_csrf_enforcement_authorized": False,
        "installed_policy": "REPORT_ONLY_UNCHANGED",
        "decision": "BLOCKED_PENDING_ROUTE_BROWSER_AND_MANUAL_EVIDENCE",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--require-strict-ready", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = build(args.root)
    except (OSError, ValueError, SyntaxError, KeyError, TypeError) as exc:
        print("CSRF_743_AUDIT=ERROR_"+type(exc).__name__, file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print("CSRF_743_UNSAFE_DECLARATIONS="+str(report["total_unsafe_declarations"]))
        print("CSRF_743_RECENT_MACD_UNQUALIFIED="+str(len(NEW_MACD)))
        print("CSRF_743_GLOBAL_STRICT=BLOCKED")
        print("CSRF_743_SOURCE_INVENTORY=PASSED")
    # Even zero gaps in a static inventory cannot prove runtime compatibility.
    if args.require_strict_ready:
        print("CSRF_743_GLOBAL_SWITCH=REFUSED_NO_RUNTIME_CLEARANCE")
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
