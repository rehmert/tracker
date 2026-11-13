#!/usr/bin/env python3
"""Release 588 strict-CSRF route-readiness: conservative source-only gap report.

Do not call this a global enforcement clearance. Reported witness paths are
source-declared expectations; only a passing isolated Chromium QA run can
supply runtime evidence for them.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Explicit source-listed browser-witness candidates, including the 588 COA upload.
# This report never claims that a browser run occurred on this invocation.
# Per-path evidence is qualified only after the relevant disposable gates pass.
BROWSER_WITNESS_CANDIDATES = frozenset({
    # Release 595: signed food journal and vendor-sheet lifecycle witnesses.
    ("POST", "/food/entry/{entry_id}/edit"),
    ("POST", "/food/entry/{entry_id}/nutrition"),
    ("POST", "/food/favorite/{product_id}"),
    ("POST", "/food/quick/{product_id}"),
    ("POST", "/food/template/save"),
    ("POST", "/food/template/{template_id}/rename"),
    ("POST", "/food/template/{template_id}/log"),
    ("POST", "/food/template/{template_id}/delete"),
    ("POST", "/vendor-prices/save"),
    ("POST", "/vendor-prices/{sheet_id}/delete"),
    # Release 594: HTTP/HTTPS signed native food and vendor-pricing forms.
    ("POST", "/food/water"),
    ("POST", "/food/water/{entry_id}/delete"),
    ("POST", "/food/entry"),
    ("POST", "/food/targets"),
    ("POST", "/food/entry/{entry_id}/delete"),
    ("POST", "/vendor-prices/shipping/save"),
    ("POST", "/vendor-prices/shipping/{rule_id}/delete"),
    ("POST", "/vendor-prices/manual"),
    ("POST", "/vendor-prices/entries/{entry_id}/edit"),
    ("POST", "/vendor-prices/entries/{entry_id}/delete"),
    # Release 593: remaining PK guarded edits, what-if and protocol library.
    ("POST", "/pk/scenarios/{sid}/doses/create-batch-checked"),
    ("POST", "/pk/workspace/{sid}/edit-dose"),
    ("POST", "/pk/workspace/{sid}/revisions/{audit_id}/restore"),
    ("POST", "/pk/what-if/preview"),
    ("POST", "/pk/what-if/multi-preview"),
    ("POST", "/pk/what-if/save"),
    ("POST", "/pk/workbench/{pid}"),
    ("POST", "/pk/library/{pid}"),
    ("PUT", "/pk/library/{pid}/{experiment_id}"),
    ("POST", "/pk/library/{pid}/compare"),
    ("DELETE", "/pk/library/{pid}/{experiment_id}"),
    # Release 592: signed batch, staged, calendar, import and transform flows.
    ("POST", "/pk/scenarios/{sid}/doses/generate-preview"),
    ("POST", "/pk/scenarios/{sid}/doses/create-batch"),
    ("POST", "/pk/scenarios/{sid}/doses/delete-batch"),
    ("POST", "/pk/scenarios/{sid}/doses/undo-delete"),
    ("POST", "/pk/scenarios/{sid}/staged-preview"),
    ("POST", "/pk/scenarios/{sid}/staged-replace"),
    ("POST", "/pk/scenarios/{sid}/calendar-preview"),
    ("POST", "/pk/scenarios/{sid}/calendar-replace"),
    ("POST", "/pk/workspace/{sid}/transform-preview"),
    ("POST", "/pk/workspace/{sid}/transform-apply"),
    ("POST", "/pk/scenarios/{sid}/duplicate"),
    ("POST", "/pk/scenarios/import-preview"),
    ("POST", "/pk/scenarios/import-confirm"),
    # Release 591: isolated HTTP/HTTPS real-browser PK scenario lifecycle.
    ("POST", "/pk/compounds"),
    ("POST", "/pk/scenarios"),
    ("PUT", "/pk/scenarios/{sid}"),
    ("DELETE", "/pk/scenarios/{sid}"),
    ("POST", "/pk/scenarios/{sid}/doses"),
    ("PUT", "/pk/scenarios/{sid}/doses/{did}"),
    ("DELETE", "/pk/scenarios/{sid}/doses/{did}"),
    ("POST", "/coas/new"),
    ("POST", "/compounds"),
    ("POST", "/compounds/{cid}/edit"),
    ("POST", "/compounds/{cid}/delete"),
    ("POST", "/vitals"),
    ("POST", "/doses"),
    ("POST", "/doses/{did}/edit"),
    ("DELETE", "/doses/{did}"),
    ("POST", "/doses/preview"),
    ("POST", "/vials/{vid}"),
    ("POST", "/vials/{vid}/reconstitute"),
    ("POST", "/vials/{vid}/filter"),
    ("POST", "/vials/{vid}/preparations/{eid}/edit"),
    ("POST", "/vials/{vid}/preparations/{eid}/delete"),
    ("POST", "/vials/bulk/validate-selection"),
    ("POST", "/vials/bulk/preview"),
    ("POST", "/vials/bulk"),
    ("POST", "/vials/bulk/delete-preview"),
    ("POST", "/vials/bulk/delete"),
})


def _loader():
    path = ROOT / "scripts/tracker_csrf_route_ledger578.py"
    spec = importlib.util.spec_from_file_location("csrf588ledger", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Missing tracked source ledger")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def report() -> dict:
    ledger = _loader().build(ROOT)
    by_path = {(r["method"], r["path"]) for r in ledger["routes"]}
    # Explicitly reject phantom source references; do not silently certify.
    absent = sorted(BROWSER_WITNESS_CANDIDATES - by_path)
    # Known signed session-account workflows are deliberately NOT folded into
    # generic global-CSRF proofs; separate account-isolation review required.
    rows = []
    for route in ledger["routes"]:
        method, path = route["method"], route["path"]
        scoped = (method, path) in BROWSER_WITNESS_CANDIDATES
        rows.append({
            "method": method, "path": path, "file": route["file"],
            "line": route["line"],
            "evidence_scope": ("candidate_strict_browser_witness"
                               if scoped else "unqualified_for_global_enforcement"),
            "runtime_verified_in_this_report": False,
            "account_isolation_verified_in_this_report": False,
        })
    status = ("BLOCKED_SOURCE_WITNESS_MISMATCH" if absent
              else "BLOCKED_INCOMPLETE_RUNTIME_CLEARANCE")
    return {
        "status": status,
        "strict_csrf_enforce_installed": False,
        "global_enable_authorized": False,
        "route_count": len(rows),
        "candidate_source_witness_count": sum(
            row["evidence_scope"] == "candidate_strict_browser_witness"
            for row in rows
        ),
        "remaining_unqualified_route_count": sum(
            row["evidence_scope"] == "unqualified_for_global_enforcement"
            for row in rows
        ),
        "missing_witness_source_routes": [{"method": m, "path": p} for m, p in absent],
        "javascript_unresolved": ledger["summary"]["js_unresolved"],
        "pending_manual_review": ledger["summary"]["pending_manual_review"],
        "mandatory_pending": [
            "Complete coverage for remaining unsafe routes including native multipart uploads",
            "Secondary-account HTTP/HTTPS signed writes and cross-account isolation",
            "Dynamic JavaScript callsites and implicit native forms",
            "Isolated full-regression and forged/cross-site checks for each newly cleared route",
            "Separate operator authorization, DEV rollout, PROD rollback and operational decision",
        ],
        "routes": rows,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json", action="store_true", help="Print deterministic JSON to stdout")
    args = p.parse_args()
    evidence = report()
    if args.json:
        print(json.dumps(evidence, indent=2, sort_keys=True))
    else:
        print("CSRF_588_READINESS=" + evidence["status"])
        print("CSRF_588_ROUTES=" + str(evidence["route_count"]))
        print("CSRF_588_CANDIDATE_WITNESS_ROUTES=" + str(evidence["candidate_source_witness_count"]))
        print("CSRF_588_UNQUALIFIED_ROUTES=" + str(evidence["remaining_unqualified_route_count"]))
        print("CSRF_588_PENDING_MANUAL_REVIEW=" + str(evidence["pending_manual_review"]))
        print("CSRF_588_INSTALLED_ENFORCEMENT=UNCHANGED_REPORT_ONLY")
    return 0 if not evidence["missing_witness_source_routes"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
