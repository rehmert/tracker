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
    assert report["new_627_source_mapped_routes"] == 27
    assert report["previously_observed_targeted_positive_routes"] == 19
    assert report["new_unexecuted_protocol_route_tests"] == 5
    assert report["new_unexecuted_blend_preview_route_tests"] == 3
    assert report["remaining_without_positive_source_witness"] == 34
    assert report["manual_review_items_unchanged"] == 110
    assert report["session_account_routes_not_certified"] == 6


def test_627_signed_route_manifest_has_no_duplicate_or_unmapped_routes():
    report = build()
    positive = report["new_627_positive_routes"]
    remaining = report["remaining_routes"]
    pkeys = {(r["method"], r["path"]) for r in positive}
    rkeys = {(r["method"], r["path"]) for r in remaining}
    assert len(pkeys) == len(positive) == 27
    assert len(rkeys) == len(remaining) == 34
    assert pkeys.isdisjoint(rkeys)
    assert len(pkeys | rkeys) == 61
    assert all(not row["full_dev_runtime_qualified"] for row in positive)
    assert sum(row["routes"] for row in report["remaining_route_workstreams"]) == 34

def test_627_blend_browser_fixture_uses_only_disposable_database():
    from pathlib import Path
    source = (Path(__file__).resolve().parent /
              "browser/test_csrf_blend_previews627.py").read_text()
    assert 'from app.db import SessionLocal' not in source
    assert 'os.environ["TRACKER_DATA_DIR"] = str(DATA)' in source
    assert 'database = DATA / "tracker.db"' in source
    assert "database.is_file()" in source
    assert "not database.is_symlink()" in source
    assert '"sqlite:///" + str(database)' in source
    assert "sessionmaker(bind=qa_engine" in source
    assert "qa_engine.dispose()" in source
