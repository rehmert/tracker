#!/usr/bin/env python3
"""Conservative Release 627 positive-route reconciliation (source only).

Never claims global enforcement readiness, and never invents runtime evidence.
Only the 27 remaining routes explicitly mapped to five 627 signed
lifecycle modules are source-mapped; eight newer protocol/preview cases remain unexecuted.
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

# Routes introduced after the frozen Release 627 historical baseline.
# Keep them explicitly unqualified until separate positive browser evidence
# is mapped; never silently fold them into original source witnesses.
POST_627_UNQUALIFIED_ROUTES = frozenset({
    ("POST", "/food/duplicates/merge"),
    ("POST", "/food/duplicates/resolve-unused"),
    ("POST", "/food/duplicates/keep-distinct"),
})

# Release 635: additional unsigned negative-matrix routes, never counted
# as positive browser proof or merged into the frozen 627 baseline.
POST_635_UNQUALIFIED_ROUTES = frozenset({
    ("POST", "/regimen/items"),
    ("POST", "/regimen/items/{item_id}/edit"),
    ("POST", "/regimen/items/{item_id}/archive"),
    ("POST", "/regimen/schedules"),
    ("POST", "/regimen/schedules/{schedule_id}/edit"),
    ("POST", "/regimen/schedules/{schedule_id}/stop"),
    ("POST", "/regimen/entries"),
    ("POST", "/regimen/entries/{entry_id}/edit"),
    ("POST", "/regimen/entries/{entry_id}/delete"),
})
POST_643_UNQUALIFIED_COA_ROUTES = frozenset({
    ("POST", "/coas/{cid}/attachments"),
    ("POST", "/coas/{cid}/attachments/{aid}/delete"),
})
POST_645_UNQUALIFIED_COA_ROUTES = frozenset({
    ("POST", "/coas/{cid}/attachments/{aid}/test-type"),
    ("POST", "/coas/{cid}/default-file"),
})
POST_647_UNQUALIFIED_COA_ROUTES = frozenset({
    ("POST", "/coas/{cid}/attachments/test-types"),
})
# Release 652: three COA catalog management writes were introduced before
# Release 653, but omitted from the earlier post-627 reconciliation ledger.
# These are explicitly unqualified, never inferred as positive browser proof.
POST_652_UNQUALIFIED_CATALOG_ROUTES = frozenset({
    ("POST", "/coa-test-types"),
    ("POST", "/coa-test-types/{type_id}/edit"),
    ("POST", "/coa-test-types/{type_id}/toggle"),
})

# Exact unsafe declarations added after the previously frozen Release 653
# source inventory. Read from the Release 653..704 router diff; these are NOT
# signed-positive CSRF witnesses. Any new/removed route changes must be reviewed
# explicitly rather than hidden by incrementing a numeric threshold.
POST_654_PLUS_UNQUALIFIED_ROUTES = frozenset({
    ("POST", "/coas/{cid}/attachments/identifiers"),
    ("POST", "/food/saved/{product_id}/edit"),
    ("POST", "/workouts/backfill"),
    ("POST", "/workouts/backfill/import.csv"),
    ("POST", "/workouts/equipment"),
    ("POST", "/workouts/equipment/{equipment_id}/load"),
    ("POST", "/workouts/equipment/{equipment_id}/settings"),
    ("POST", "/workouts/finish"),
    ("POST", "/workouts/finish-review"),
    ("POST", "/workouts/quick/finish"),
    ("POST", "/workouts/quick/offline-sync"),
    ("POST", "/workouts/quick/repeat"),
    ("POST", "/workouts/quick/routines/{routine_id}/start"),
    ("POST", "/workouts/quick/sets"),
    ("POST", "/workouts/quick/start"),
    ("POST", "/workouts/routines"),
    ("POST", "/workouts/routines/{routine_id}/duplicate"),
    ("POST", "/workouts/routines/{routine_id}/equipment"),
    ("POST", "/workouts/routines/{routine_id}/groups"),
    ("POST", "/workouts/routines/{routine_id}/groups/{group_id}/remove"),
    ("POST", "/workouts/routines/{routine_id}/items/{item_id}/move"),
    ("POST", "/workouts/routines/{routine_id}/items/{item_id}/remove"),
    ("POST", "/workouts/routines/{routine_id}/items/{item_id}/substitute"),
    ("POST", "/workouts/routines/{routine_id}/program/import"),
    ("POST", "/workouts/routines/{routine_id}/program/import.csv"),
    ("POST", "/workouts/routines/{routine_id}/program/items/{item_id}"),
    ("POST", "/workouts/routines/{routine_id}/program/rest"),
    ("POST", "/workouts/routines/{routine_id}/schedule"),
    ("POST", "/workouts/routines/{routine_id}/schedule/clear"),
    ("POST", "/workouts/routines/{routine_id}/start"),
    ("POST", "/workouts/sessions/{session_id}/reuse-as-routine"),
    ("POST", "/workouts/sessions/{session_id}/sets/{set_id}/correct"),
    ("POST", "/workouts/sessions/{session_id}/sets/{set_id}/corrections/{change_id}/undo"),
    ("POST", "/workouts/sets"),
    ("POST", "/workouts/sets/repeat"),
    ("POST", "/workouts/sets/{set_id}/delete"),
    ("POST", "/workouts/sets/{set_id}/edit"),
    ("POST", "/workouts/start"),
})

POST_BASELINE_ADDITIONS = (
    POST_627_UNQUALIFIED_ROUTES |
    POST_635_UNQUALIFIED_ROUTES |
    POST_643_UNQUALIFIED_COA_ROUTES | POST_645_UNQUALIFIED_COA_ROUTES |
    POST_647_UNQUALIFIED_COA_ROUTES | POST_652_UNQUALIFIED_CATALOG_ROUTES
)
CURRENT_UNQUALIFIED_ADDITIONS = (
    POST_BASELINE_ADDITIONS | POST_654_PLUS_UNQUALIFIED_ROUTES
)


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
    "tests/browser/test_csrf_blend_previews627.py": (
        ("POST", "/blends/preview"),
        ("POST", "/blends/reconstitution-preview"),
        ("POST", "/blends/waterfall/preview"),
    ),
    "tests/browser/test_csrf_protocol_remaining627.py": (
        ("POST", "/protocols/{pid}/calc"),
        ("POST", "/protocols/{pid}/dates"),
        ("POST", "/protocols/{pid}/save"),
        ("POST", "/protocols/{pid}/add-item"),
        ("POST", "/protocols/{pid}/duplicate"),
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
    "tests/browser/test_csrf_blend_previews627.py": (
        'preview("/blends/preview",',
        'preview("/blends/reconstitution-preview",',
        'preview("/blends/waterfall/preview",',
        'assert db.query(Blend).count() == baseline_blends',
        'denied.status == 403',
        'result["status"] == 200',
    ),
    "tests/browser/test_csrf_protocol_remaining627.py": (
        'signed(location + "/calc",',
        'signed(location + "/dates",',
        'signed(location + "/save",',
        'signed(location + "/add-item",',
        'signed(location + "/duplicate",',
        'SELECT amount_value,amount_unit FROM protocol_items',
        'SELECT count(*) FROM protocol_items',
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
        min_forged_calls = 1 if module == "tests/browser/test_csrf_blend_previews627.py" else 2
        if src.count("max_redirects=0") < min_forged_calls or "status == 403" not in src:
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

    if len(mapped) != 27 or not set(mapped) <= remaining or set(mapped) & known:
        raise ValueError("Release 627 source witnesses differ from baseline gap")
    # Preserve the exact historic 144/83/61 Release 627 source baseline,
    # explicitly accounting for 20 pre-653 additions (including three
    # Release 652 COA catalog routes) and 38 Release 654..704 additions.
    # No new route receives positive witness credit from this inventory.
    missing = CURRENT_UNQUALIFIED_ADDITIONS - remaining
    misclassified = CURRENT_UNQUALIFIED_ADDITIONS & known
    actual_total = report["total_unsafe_routes"]
    expected_total = 144 + len(CURRENT_UNQUALIFIED_ADDITIONS)
    expected_remaining = 61 + len(CURRENT_UNQUALIFIED_ADDITIONS)
    if (len(POST_652_UNQUALIFIED_CATALOG_ROUTES) != 3
            or len(POST_654_PLUS_UNQUALIFIED_ROUTES) != 38
            or len(POST_BASELINE_ADDITIONS) != 20
            or POST_BASELINE_ADDITIONS & POST_654_PLUS_UNQUALIFIED_ROUTES
            or actual_total != expected_total
            or len(known) != 83
            or len(remaining) != expected_remaining
            or missing or misclassified):
        raise ValueError(
            "Unsafe-route inventory differs from pinned 627+705 evidence; "
            f"actual_total={actual_total} expected_total={expected_total} "
            f"candidate_count={len(known)} expected_candidates=83 "
            f"unqualified_count={len(remaining)} expected_unqualified={expected_remaining} "
            f"missing_explicit={sorted(missing)} "
            f"misclassified_as_candidates={sorted(misclassified)}; "
            "manual reassessment required"
        )

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
        "post_627_unqualified_routes": [
            {"method": method, "path": path}
            for method, path in sorted(POST_627_UNQUALIFIED_ROUTES)
        ],
        "post_652_unqualified_catalog_routes": [
            {"method": method, "path": path}
            for method, path in sorted(POST_652_UNQUALIFIED_CATALOG_ROUTES)
        ],
        "current_unsafe_routes": report["total_unsafe_routes"],
        "historical_653_unsafe_routes": 144 + len(POST_BASELINE_ADDITIONS),
        "post_654_plus_unqualified_routes": [
            {"method": method, "path": path}
            for method, path in sorted(POST_654_PLUS_UNQUALIFIED_ROUTES)
        ],
        "post_634_unqualified_regimen_routes": [
            {"method": method, "path": path}
            for method, path in sorted(POST_635_UNQUALIFIED_ROUTES)
        ],
        "post_643_unqualified_coa_routes": [
            {"method": method, "path": path}
            for method, path in sorted(POST_643_UNQUALIFIED_COA_ROUTES)
        ],
        "post_647_unqualified_coa_routes": [
            {"method": method, "path": path}
            for method, path in sorted(POST_647_UNQUALIFIED_COA_ROUTES)
        ],
        "pre_627_candidate_routes": 83,
        "pre_627_unqualified_routes": 61,
        "new_627_source_mapped_routes": len(mapped),
        "previously_observed_targeted_positive_routes": 19,
        "new_unexecuted_protocol_route_tests": 5,
        "new_unexecuted_blend_preview_route_tests": 3,
        "new_627_positive_routes": [
            {"method": method, "path": path, "test_module": module,
             "full_dev_runtime_qualified": False}
            for (method, path), module in sorted(mapped.items())
        ],
        "remaining_without_positive_source_witness": len(uncovered),
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
              str(result["new_627_source_mapped_routes"]))
        print("CSRF_627_STILL_WITHOUT_POSITIVE_WITNESS=" +
              str(result["remaining_without_positive_source_witness"]))
        print("CSRF_627_MANUAL_REVIEW_UNCHANGED=" +
              str(result["manual_review_items_unchanged"]))
        print("CSRF_627_GLOBAL_ENFORCEMENT=BLOCKED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
