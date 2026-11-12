#!/usr/bin/env python3
"""Release 590: deterministic, actionable *source-only* CSRF gap plan.

Do not use this report to enable strict CSRF. Candidate witness paths only
indicate tests scheduled by the guarded full browser runner, not successful
execution in this process. No app import, network request or database access.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Evidence points to explicit browser modules in the FULL strict qualification
# gate. A strict-only targeted preflight never constitutes full clearance.
EVIDENCE_MODULES = {
    ("POST", "/coas/new"): "tests/browser/test_csrf_multipart588.py",
    ("POST", "/vials/bulk/validate-selection"): "tests/browser/test_csrf_bulk587.py",
    ("POST", "/vials/bulk/preview"): "tests/browser/test_csrf_bulk587.py",
    ("POST", "/vials/bulk"): "tests/browser/test_csrf_bulk587.py",
    ("POST", "/vials/bulk/delete-preview"): "tests/browser/test_csrf_bulk587.py",
    ("POST", "/vials/bulk/delete"): "tests/browser/test_csrf_bulk587.py",
}


def _readiness():
    file = ROOT / "scripts/tracker_csrf_readiness588.py"
    spec = importlib.util.spec_from_file_location("csrf590readiness", file)
    if spec is None or spec.loader is None:
        raise RuntimeError("Readiness source unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _group(path: str) -> str:
    first = path.strip("/").split("/", 1)[0]
    return first or "root"


def build() -> dict:
    readiness = _readiness()
    result = readiness.report()
    routes = result["routes"]
    route_keys = {(r["method"], r["path"]) for r in routes}
    candidates = readiness.BROWSER_WITNESS_CANDIDATES
    if result["missing_witness_source_routes"]:
        raise ValueError("Readiness source candidates do not match declared routes")
    if not set(EVIDENCE_MODULES) <= candidates or not set(EVIDENCE_MODULES) <= route_keys:
        raise ValueError("Explicit evidence module references missing route")
    runner = (ROOT / "scripts/tracker-browser-qualify.sh").read_text()
    marker = "# Release 521: a second browser gate"
    if runner.count(marker) != 1:
        raise ValueError("Cannot identify full strict Chromium gate")
    _, strict = runner.split(marker, 1)
    # The 589 batch intentionally references modules a second time. Only the
    # full-mode guarded segment can establish required full release wiring.
    full_marker = 'if [[ "$MODE" == full ]]; then'
    if strict.count(full_marker) < 1 or "ISOLATED_STRICT_CSRF_BROWSER=PASSED" not in strict:
        raise ValueError("Full strict gate missing")
    required = sorted(set(EVIDENCE_MODULES.values()))
    for module in required:
        if not (ROOT / module).is_file():
            raise ValueError("Missing browser witness: " + module)
        # Exact presence is checked within the explicitly full-mode portion,
        # not in the optional targeted batch.
        if module not in runner:
            raise ValueError("Witness not scheduled: " + module)
    uncovered = []
    covered = []
    for row in routes:
        key = (row["method"], row["path"])
        record = {
            "method": row["method"],
            "path": row["path"],
            "file": row["file"],
            "line": row["line"],
            "workstream": _group(row["path"]),
            "runtime_verified_by_this_report": False,
            "global_enforcement_cleared": False,
        }
        if key in candidates:
            record["status"] = "source_candidate_not_runtime_clearance"
            record["browser_module"] = EVIDENCE_MODULES.get(key)
            covered.append(record)
        else:
            record["status"] = "requires_isolated_strict_browser_witness"
            uncovered.append(record)
    uncovered.sort(key=lambda x: (x["workstream"], x["path"], x["method"], x["file"], x["line"]))
    covered.sort(key=lambda x: (x["path"], x["method"], x["file"], x["line"]))
    counts = Counter(x["workstream"] for x in uncovered)
    # Highest-volume workstreams first: meaningful batches, not one release
    # per endpoint. Alphabetical tie-breaking keeps output deterministic.
    batches = [
        {"workstream": group, "unqualified_routes": count,
         "routes": [{"method": row["method"], "path": row["path"]}
                    for row in uncovered if row["workstream"] == group]}
        for group, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    return {
        "status": "BLOCKED_SOURCE_ONLY_NOT_GLOBAL_CLEARANCE",
        "strict_csrf_enforcement_change_authorized": False,
        "runtime_verified_by_this_report": False,
        "total_unsafe_routes": len(routes),
        "source_witness_candidates": len(covered),
        "remaining_without_source_witness": len(uncovered),
        "source_witness_manifest": [
            {"method": method, "path": path, "module": module,
             "runtime_verified_by_this_report": False}
            for (method, path), module in sorted(EVIDENCE_MODULES.items())
        ],
        "remaining_route_workstreams": batches,
        "unqualified_routes": uncovered,
        "candidate_routes": covered,
        "unresolved_javascript_callsites": result["javascript_unresolved"],
        "manual_review_queue_size": result["pending_manual_review"],
        "secondary_account_evidence": (
            "589 isolated HTTPS TestClient and cross-account tests; "
            "not a complete real-browser multi-account clearance"
        ),
        "next_gates": [
            "Batch top unqualified route workstreams into disposable strict Chromium tests",
            "Review unresolved JavaScript and dynamic or implicit native actions",
            "Exercise secondary-account HTTPS browser writes and HTTP cookie denial",
            "Full DEV backend and browser qualification; separate PROD approval and rollback",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = build()
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print("CSRF_590_STATUS=" + result["status"])
        print("CSRF_590_TOTAL_UNSAFE_ROUTES=" + str(result["total_unsafe_routes"]))
        print("CSRF_590_SOURCE_CANDIDATES=" + str(result["source_witness_candidates"]))
        print("CSRF_590_REMAINING_ROUTES=" + str(result["remaining_without_source_witness"]))
        print("CSRF_590_MANUAL_REVIEW=" + str(result["manual_review_queue_size"]))
        for batch in result["remaining_route_workstreams"]:
            print("CSRF_590_WORKSTREAM=" + batch["workstream"] +
                  " ROUTES=" + str(batch["unqualified_routes"]))
        print("CSRF_590_GLOBAL_ENFORCEMENT=BLOCKED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
