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
    # Release 597: signed purchase and supply inventory lifecycle.
    ("POST", "/purchases"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/purchases/{pid}"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/supplies"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/supplies/{sid}/use"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/supplies/{sid}/dose"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/supplies/categories"): "tests/browser/test_strict_csrf521.py",
    # Release 596: signed vendor multipart, import and preview workflows.
    ("POST", "/vendor-prices/attachments/upload"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/vendor-prices/attachments/{attachment_id}/delete"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/vendor-prices/items-csv/preview"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/vendor-prices/items-csv/save"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/vendor-prices/bulk/preview"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/vendor-prices/bulk/save"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/vendor-prices/preview"): "tests/browser/test_strict_csrf521.py",
    # Release 595: signed food journal and vendor-sheet lifecycle witnesses.
    ("POST", "/food/entry/{entry_id}/edit"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/food/entry/{entry_id}/nutrition"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/food/favorite/{product_id}"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/food/quick/{product_id}"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/food/template/save"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/food/template/{template_id}/rename"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/food/template/{template_id}/log"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/food/template/{template_id}/delete"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/vendor-prices/save"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/vendor-prices/{sheet_id}/delete"): "tests/browser/test_strict_csrf521.py",
    # Release 594: HTTP/HTTPS signed native food and vendor-pricing forms.
    ("POST", "/food/water"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/food/water/{entry_id}/delete"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/food/entry"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/food/targets"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/food/entry/{entry_id}/delete"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/vendor-prices/shipping/save"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/vendor-prices/shipping/{rule_id}/delete"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/vendor-prices/manual"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/vendor-prices/entries/{entry_id}/edit"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/vendor-prices/entries/{entry_id}/delete"): "tests/browser/test_strict_csrf521.py",
    # Release 593: actual browser-signed guarded scenario, what-if and
    # experiment library operations, including persisted revisions.
    ("POST", "/pk/scenarios/{sid}/doses/create-batch-checked"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/pk/workspace/{sid}/edit-dose"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/pk/workspace/{sid}/revisions/{audit_id}/restore"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/pk/what-if/preview"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/pk/what-if/multi-preview"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/pk/what-if/save"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/pk/workbench/{pid}"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/pk/library/{pid}"): "tests/browser/test_strict_csrf521.py",
    ("PUT", "/pk/library/{pid}/{experiment_id}"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/pk/library/{pid}/compare"): "tests/browser/test_strict_csrf521.py",
    ("DELETE", "/pk/library/{pid}/{experiment_id}"): "tests/browser/test_strict_csrf521.py",
    # Release 592: signed schedule and import workflows share the same
    # mandatory full strict Chromium module; negative-only probes are excluded.
    ("POST", "/pk/scenarios/{sid}/doses/generate-preview"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/pk/scenarios/{sid}/doses/create-batch"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/pk/scenarios/{sid}/doses/delete-batch"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/pk/scenarios/{sid}/doses/undo-delete"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/pk/scenarios/{sid}/staged-preview"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/pk/scenarios/{sid}/staged-replace"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/pk/scenarios/{sid}/calendar-preview"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/pk/scenarios/{sid}/calendar-replace"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/pk/workspace/{sid}/transform-preview"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/pk/workspace/{sid}/transform-apply"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/pk/scenarios/{sid}/duplicate"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/pk/scenarios/import-preview"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/pk/scenarios/import-confirm"): "tests/browser/test_strict_csrf521.py",
    # Release 591: same mandatory strict Chromium module already wired
    # into the full qualification. These seven routes have real signed
    # lifecycle tests, not just unsigned denial checks.
    ("POST", "/pk/compounds"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/pk/scenarios"): "tests/browser/test_strict_csrf521.py",
    ("PUT", "/pk/scenarios/{sid}"): "tests/browser/test_strict_csrf521.py",
    ("DELETE", "/pk/scenarios/{sid}"): "tests/browser/test_strict_csrf521.py",
    ("POST", "/pk/scenarios/{sid}/doses"): "tests/browser/test_strict_csrf521.py",
    ("PUT", "/pk/scenarios/{sid}/doses/{did}"): "tests/browser/test_strict_csrf521.py",
    ("DELETE", "/pk/scenarios/{sid}/doses/{did}"): "tests/browser/test_strict_csrf521.py",
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
    # Release 521 is mandatory in the standard full strict pass, not in
    # the optional 589 replay. Verify both its runner wiring and the
    # concrete 591 PK test function before counting these routes.
    pk_module = "tests/browser/test_strict_csrf521.py"
    if pk_module in required:
        pk_source = (ROOT / pk_module).read_text()
        if ("def test_591_pk_scenario_json_lifecycle_signed_and_unsigned_rejected(" not in pk_source
                or "def test_592_pk_schedule_batch_import_calendar_and_transform_signed(" not in pk_source
                or "def test_593_pk_checked_batch_guarded_edit_and_revision_restore(" not in pk_source
                or "def test_593_pk_what_if_preview_multi_and_save(" not in pk_source
                or "def test_593_pk_workbench_and_experiment_library_signed(" not in pk_source):
            raise ValueError("PK 591 browser witness missing")
        if strict.count(pk_module) != 1:
            raise ValueError("PK 591 witness not exactly once in full strict gate")
    # Release 594: validate the actual positive form witness, not just a
    # tokenless rejection matrix. Full Chromium still supplies runtime proof.
    if any(route[1].startswith(("/food/", "/vendor-prices/"))
           for route in EVIDENCE_MODULES):
        browser_source = (ROOT / "tests/browser/test_strict_csrf521.py").read_text()
        if ("def test_594_food_vendor_signed_forms_and_unsigned_denial(" not in browser_source
                or "def test_595_food_templates_corrections_and_vendor_sheets(" not in browser_source
                or "def test_596_vendor_multipart_and_csv_roundtrip_signed(" not in browser_source):
            raise ValueError("Food/vendor 594 browser witness missing")
    # Source-only route qualification must include a real Chromium purchase
    # and supply-inventory lifecycle, not negative-only CSRF probes.
    if any(path.startswith(("/purchases", "/supplies"))
           for _, path in EVIDENCE_MODULES):
        browser_source = (ROOT / "tests/browser/test_strict_csrf521.py").read_text()
        if "def test_597_purchase_and_supply_inventory_signed(" not in browser_source:
            raise ValueError("Purchase/supply 597 browser witness missing")
    # Delimit the actual combined 587/588 full-only gate. A targeted-only
    # replay cannot satisfy the qualification requirement.
    full_section_start = "# Combined Release 587–588: isolate bulk inventory browser writes"
    full_section_end = 'if [[ "$MODE" == targeted && "${TARGETED_MODULE##*/}" == test_csrf_multipart588.py ]]; then'
    if strict.count(full_section_start) != 1 or strict.count(full_section_end) != 1:
        raise ValueError("Full 587/588 browser gate boundaries changed")
    full_section = strict.split(full_section_start, 1)[1].split(full_section_end, 1)[0]
    if full_marker not in full_section:
        raise ValueError("Witness section not full-mode guarded")
    for module in required:
        if not (ROOT / module).is_file():
            raise ValueError("Missing browser witness: " + module)
        if module != pk_module and full_section.count(module) != 1:
            raise ValueError("Witness not scheduled exactly once in full gate: " + module)
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
