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


def test_627_targeted_allowlist_preserves_release584_contract():
    from pathlib import Path
    runner = (Path(__file__).resolve().parents[1] /
              "scripts/tracker-browser-qualify.sh").read_text()
    legacy = ('[[ "$TARGETED_MODULE" == csrf-batch589 || "$TARGETED_MODULE" '
              '=~ ^tests/browser/test_(csrf_preparations583|form_overlap586|'
              'csrf_bulk587|csrf_multipart588)[.]py$ ]]')
    assert legacy in runner
    extension = ('[[ "$TARGETED_MODULE" == csrf-batch627 || '
                 '"$TARGETED_MODULE" == csrf-positive627 || '
                 '"$TARGETED_MODULE" == csrf-new627 ]]')
    assert extension in runner
    assert runner.index(legacy) < runner.index(extension)
    assert 'ISOLATED_STRICT_CSRF_BROWSER=PASSED' in runner


def test_627_coa_upload_asserts_rendered_saved_field_not_body_text():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    for module, marker in (
        ("tests/browser/test_csrf_multipart588.py", "name"),
        ("tests/browser/test_csrf_coa_lifecycle627.py", "lab"),
    ):
        source = (root / module).read_text()
        expected = "expect(page.locator('input[name=\"lab_name\"]')).to_have_value(" + marker + ")"
        assert expected in source, module
        assert 'expect(page.locator("body")).to_contain_text(' + marker + ')' not in source
        assert "View existing document" in source


def test_627_release511_inventory_scopes_new_browser_modules_strict_only():
    from pathlib import Path
    from importlib.util import module_from_spec, spec_from_file_location

    root = Path(__file__).resolve().parents[1]
    spec = spec_from_file_location("release511_inventory627",
                                   root / "tests/test_browser_qualification511.py")
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    new_modules = {
        "tests/browser/test_csrf_gap627.py",
        "tests/browser/test_csrf_signed_lifecycles627.py",
        "tests/browser/test_csrf_purchase_children627.py",
        "tests/browser/test_csrf_coa_lifecycle627.py",
        "tests/browser/test_csrf_protocol_remaining627.py",
        "tests/browser/test_csrf_blend_previews627.py",
    }
    assert new_modules <= module.STRICT_ONLY
    source = (root / "scripts/tracker-browser-qualify.sh").read_text()
    standard, strict = source.split(module.STRICT_PASS_MARKER, 1)
    for name in new_modules:
        assert name not in standard
        assert strict.count(name) >= 2  # guarded full + optional targeted replay
    # The original Release 511 test verifies exact full-gate cardinality.
    module.test_511_every_browser_module_in_disposable_qualification()


def test_627_full_browser_workers_follow_release628_16_worker_standard():
    from pathlib import Path
    runner = (Path(__file__).resolve().parents[1] /
              "scripts/tracker-browser-qualify.sh").read_text()
    # Two main browser gates plus one shared per-module runner.
    assert runner.count("-n 16 --dist=loadfile") == 3
    assert 'echo "WORKERS=16"' in runner
    assert "WORKERS=4" not in runner and "WORKERS=1" not in runner
    assert '"$PY" -B -m pytest -n 16 --dist=loadfile' in runner
    assert 'rc=${PIPESTATUS[0]}' in runner
