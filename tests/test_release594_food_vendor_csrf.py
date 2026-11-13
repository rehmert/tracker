"""Release 594: source-only CSRF witnesses for food and vendor pricing."""
from __future__ import annotations

import ast
from pathlib import Path

from scripts import tracker_csrf_gap_plan590 as gap
from scripts import tracker_csrf_readiness588 as readiness

ROOT = Path(__file__).resolve().parents[1]
ROUTES = frozenset({
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
})


def test_594_scope_and_route_counts_remain_source_only():
    assert len(ROUTES) == 10
    assert ROUTES <= readiness.BROWSER_WITNESS_CANDIDATES
    assert ROUTES <= set(gap.EVIDENCE_MODULES)
    assert {gap.EVIDENCE_MODULES[k] for k in ROUTES} == {
        "tests/browser/test_strict_csrf521.py"
    }
    report = readiness.report()
    assert not report["missing_witness_source_routes"]
    assert report["status"] == "BLOCKED_INCOMPLETE_RUNTIME_CLEARANCE"
    assert report["global_enable_authorized"] is False
    assert report["strict_csrf_enforce_installed"] is False
    plan = gap.build()
    assert plan["status"] == "BLOCKED_SOURCE_ONLY_NOT_GLOBAL_CLEARANCE"
    assert plan["source_witness_candidates"] == 70
    assert plan["remaining_without_source_witness"] == 74
    assert len(plan["source_witness_manifest"]) == 57
    assert plan["runtime_verified_by_this_report"] is False
    assert plan["strict_csrf_enforcement_change_authorized"] is False
    # No accidental blanket clearance for remaining food/vendor operations.
    assert any(row["path"].startswith("/food/") for row in plan["unqualified_routes"])
    assert any(row["path"].startswith("/vendor-prices/") for row in plan["unqualified_routes"])


def test_594_real_chromium_signed_form_witness_and_disposable_db():
    source = (ROOT / "tests/browser/test_strict_csrf521.py").read_text()
    ast.parse(source)
    marker = "def test_594_food_vendor_signed_forms_and_unsigned_denial("
    assert source.count(marker) == 1
    before, after = source.split(marker, 1)
    assert '@pytest.mark.parametrize("scheme", ("http", "https"))' in before[-130:]
    assert 'with page.expect_response(' in after
    assert 'await fetch(route, {' in after
    assert 'assert response.status == expected' in after
    assert 'response.request.all_headers().get("x-tracker-csrf") == token' in after
    assert 'response.headers.get("x-tracker-csrf-report") == "valid"' in after
    assert 'assert response.status == 403' in after
    assert 'DATA.parent.parent == Path("/tmp").resolve()' in after
    assert 'database.is_file() and not database.is_symlink()' in after
    for route in (
        '"/food/water"', '"/food/entry"', '"/food/targets"',
        '"/vendor-prices/shipping/save"', '"/vendor-prices/manual"',
        '"/vendor-prices/entries/{entry_id}/edit"',
    ):
        # Dynamic entries use f-strings; source checks are scoped to
        # meaningful endpoint prefixes for those cases.
        if "{entry_id}" in route:
            assert 'f"/vendor-prices/entries/{entry_id}/edit"' in after
        else:
            assert route in after
    for persistence in (
        "tracker_water_entries", "tracker_food_entries",
        "tracker_food_targets", "vendor_shipping_rules", "vendor_price_entries",
    ):
        assert persistence in after
    runner = (ROOT / "scripts/tracker-browser-qualify.sh").read_text()
    _, strict = runner.split("# Release 521: a second browser gate", 1)
    assert strict.count("tests/browser/test_strict_csrf521.py") == 1
    assert runner.count("ISOLATED_STRICT_CSRF_BROWSER=PASSED") == 1


def test_594_oom_recovery_keeps_every_browser_gate_with_bounded_parallelism():
    runner = (ROOT / "scripts/tracker-browser-qualify.sh").read_text()
    assert runner.count("-n 4 --dist=loadfile") == 3
    assert "-n 16 --dist=loadfile" not in runner
    assert 'echo "WORKERS=4"' in runner
    assert "tests/browser/test_strict_csrf521.py" in runner
    assert "tests/browser/test_food_search_ui.py" in runner
    assert "ISOLATED_BROWSER=PASSED" in runner
    assert "ISOLATED_STRICT_CSRF_BROWSER=PASSED" in runner
    assert "STRICT_BROWSER_PYTEST_EXIT=" in runner
    assert "BROWSER_PYTEST_EXIT=" in runner
