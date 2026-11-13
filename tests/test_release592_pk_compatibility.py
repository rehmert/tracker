"""Release 592: strict PK schedule and import browser witness contract."""
from __future__ import annotations

import ast
from pathlib import Path

from scripts import tracker_csrf_gap_plan590 as gap
from scripts import tracker_csrf_readiness588 as readiness

ROOT = Path(__file__).resolve().parents[1]

PK_592 = frozenset({
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
})


def test_592_all_new_positive_routes_are_source_witnesses_not_clearance():
    assert len(PK_592) == 13
    assert PK_592 <= readiness.BROWSER_WITNESS_CANDIDATES
    assert PK_592 <= set(gap.EVIDENCE_MODULES)
    assert {gap.EVIDENCE_MODULES[k] for k in PK_592} == {
        "tests/browser/test_strict_csrf521.py"
    }
    report = readiness.report()
    assert report["missing_witness_source_routes"] == []
    assert report["global_enable_authorized"] is False
    assert report["strict_csrf_enforce_installed"] is False
    assert report["status"] == "BLOCKED_INCOMPLETE_RUNTIME_CLEARANCE"
    plan = gap.build()
    assert plan["status"] == "BLOCKED_SOURCE_ONLY_NOT_GLOBAL_CLEARANCE"
    assert plan["strict_csrf_enforcement_change_authorized"] is False
    assert plan["runtime_verified_by_this_report"] is False
    assert len(plan["source_witness_manifest"]) == 70
    assert PK_592 <= {
        (row["method"], row["path"]) for row in plan["candidate_routes"]
    }
    assert not any(row["path"].startswith("/pk/") for row in plan["unqualified_routes"])
    assert plan["remaining_without_source_witness"] > 0


def test_592_browser_witness_has_signed_and_forged_full_workflows():
    browser = (ROOT / "tests/browser/test_strict_csrf521.py").read_text()
    ast.parse(browser)
    marker = "def test_592_pk_schedule_batch_import_calendar_and_transform_signed("
    assert browser.count(marker) == 1
    head, body = browser.split(marker, 1)
    assert '@pytest.mark.parametrize("scheme", ("http", "https"))' in head[-130:]
    assert 'window.trackerCsrfToken' in body
    assert 'page.request.fetch(' in body
    assert 'assert response.status == 403' in body
    assert "await fetch(route, {" in body
    assert 'assert result["csrf"] == "valid"' in body
    assert 'pending.value.request.all_headers().get("x-tracker-csrf") == token' in body
    for operation in (
        'generate-preview', 'create-batch', 'delete-batch', 'undo-delete',
        'staged-preview', 'staged-replace',
        'calendar-preview', 'calendar-replace',
        'transform-preview', 'transform-apply',
        '/duplicate', '/pk/scenarios/import-preview',
        '/pk/scenarios/import-confirm',
    ):
        assert operation in body, operation
    for evidence in (
        'assert current(sid, cid)["doses"] == []',
        'assert restored["restored"] == 2',
        'assert after != before',
        'projected["saved"] is False',
        'assert applied["updated"] == 2',
        'assert copy_id != sid',
        'assert [x["amount_mg"] for x in current(imported_id, cid)["doses"]]',
        'for candidate in (imported_id, copy_id, sid):',
    ):
        assert evidence in body, evidence


def test_592_complete_pk_unsafe_matrix_includes_multiline_import_confirm():
    browser = (ROOT / "tests/browser/test_strict_csrf521.py").read_text()
    assert '("POST", "/pk/scenarios/import-confirm")' in browser
    assert 'assert len(PK_UNSIGNED_ROUTES_591) == 31' in browser
    assert 'def test_591_pk_unsafe_route_forgery_matrix_negative_only(' in browser
    assert "TRACKER_TEST_STRICT_CSRF" in browser
    assert "TRACKER_TEST_ISOLATED" in browser
    policy = (ROOT / "app/csrf_enforcement520.py").read_text()
    assert 'os.environ.get("TRACKER_CSRF_ENFORCE", "0") == "1"' in policy
    runner = (ROOT / "scripts/tracker-browser-qualify.sh").read_text()
    strict = runner.split("# Release 521: a second browser gate", 1)[1]
    assert strict.count("tests/browser/test_strict_csrf521.py") == 1
    assert runner.count("ISOLATED_STRICT_CSRF_BROWSER=PASSED") == 1
