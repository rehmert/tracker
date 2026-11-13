"""Release 595: exact signed browser scope for food and vendor sheet workflows."""
from __future__ import annotations

import ast
from pathlib import Path

from scripts import tracker_csrf_readiness588 as readiness
from scripts import tracker_csrf_gap_plan590 as gap

ROOT = Path(__file__).resolve().parents[1]
ROUTES = frozenset({
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
})


def test_595_exact_witness_scope_and_no_clearance():
    assert len(ROUTES) == 10
    assert ROUTES <= readiness.BROWSER_WITNESS_CANDIDATES
    assert ROUTES <= set(gap.EVIDENCE_MODULES)
    assert {gap.EVIDENCE_MODULES[route] for route in ROUTES} == {
        "tests/browser/test_strict_csrf521.py"
    }
    report = readiness.report()
    assert report["missing_witness_source_routes"] == []
    assert report["global_enable_authorized"] is False
    assert report["strict_csrf_enforce_installed"] is False
    assert report["status"] == "BLOCKED_INCOMPLETE_RUNTIME_CLEARANCE"
    plan = gap.build()
    assert plan["source_witness_candidates"] == 77
    assert plan["remaining_without_source_witness"] == 67
    assert len(plan["source_witness_manifest"]) == 64
    assert plan["runtime_verified_by_this_report"] is False
    assert plan["strict_csrf_enforcement_change_authorized"] is False
    assert any(x["path"].startswith("/food/") for x in plan["unqualified_routes"])
    assert any(x["path"].startswith("/vendor-prices/") for x in plan["unqualified_routes"])


def test_595_browser_fixture_runs_both_transports_and_checks_persistence():
    path = ROOT / "tests/browser/test_strict_csrf521.py"
    source = path.read_text()
    ast.parse(source)
    marker = "def test_595_food_templates_corrections_and_vendor_sheets("
    assert source.count(marker) == 1
    head, body = source.split(marker, 1)
    assert '@pytest.mark.parametrize("scheme", ("http", "https"))' in head[-140:]
    assert 'with page.expect_response(lambda response:' in body
    assert 'response.request.all_headers().get("x-tracker-csrf") == token' in body
    assert 'response.headers.get("x-tracker-csrf-report") == "valid"' in body
    assert 'assert response.status == 403' in body
    assert 'DATA.parent.parent == Path("/tmp").resolve()' in body
    assert 'database.is_file() and not database.is_symlink()' in body
    for evidence in (
        '"/food/entry/{entry_id}/edit"',
        '"/food/entry/{entry_id}/nutrition"',
        '"/food/favorite/{revised_id}"',
        '"/food/quick/{revised_id}"',
        '"/food/template/save"',
        '"/food/template/{tid}/rename"',
        '"/food/template/{tid}/log"',
        '"/food/template/{tid}/delete"',
        '"/vendor-prices/save"',
        '"/vendor-prices/{sid}/delete"',
        'revised_id != product_id',
        'tracker_food_meal_template_items',
        'tracker_food_entries WHERE eaten_on=?',
        'vendor_price_entries WHERE sheet_id=?',
    ):
        assert evidence in body, evidence
    runner = (ROOT / "scripts/tracker-browser-qualify.sh").read_text()
    _, strict = runner.split("# Release 521: a second browser gate", 1)
    assert strict.count("tests/browser/test_strict_csrf521.py") == 1
    assert runner.count("-n 4 --dist=loadfile") == 3
    assert runner.count("ISOLATED_STRICT_CSRF_BROWSER=PASSED") == 1
