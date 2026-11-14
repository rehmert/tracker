"""Release 627 source reconciliation contracts; no production runtime effects."""
from scripts.tracker_csrf_reconcile627 import build


def test_627_signed_route_reconciliation_stays_blocked():
    report = build()
    assert report["status"] == "BLOCKED_PENDING_FULL_DEV_AND_MANUAL_REVIEW"
    assert report["global_enforcement_authorized"] is False
    assert report["full_dev_qualification_observed_by_this_report"] is False
    assert report["original_unsafe_routes"] == 144
    assert report["pre_627_candidate_routes"] == 83
    assert report["pre_627_unqualified_routes"] == 61
    assert report["new_627_targeted_positive_route_witnesses"] == 19
    assert report["remaining_without_positive_route_witness"] == 42
    assert report["manual_review_items_unchanged"] == 110
    assert report["session_account_routes_not_certified"] == 6


def test_627_signed_route_manifest_has_no_duplicate_or_unmapped_routes():
    report = build()
    positive = report["new_627_positive_routes"]
    remaining = report["remaining_routes"]
    pkeys = {(r["method"], r["path"]) for r in positive}
    rkeys = {(r["method"], r["path"]) for r in remaining}
    assert len(pkeys) == len(positive) == 19
    assert len(rkeys) == len(remaining) == 42
    assert pkeys.isdisjoint(rkeys)
    assert len(pkeys | rkeys) == 61
    assert all(not row["full_dev_runtime_qualified"] for row in positive)
    assert sum(row["routes"] for row in report["remaining_route_workstreams"]) == 42
