"""Release 597: signed purchase/supply full-browser source witnesses."""
from __future__ import annotations

import ast
from pathlib import Path

from scripts import tracker_csrf_readiness588 as readiness
from scripts import tracker_csrf_gap_plan590 as gap

ROOT=Path(__file__).resolve().parents[1]
ROUTES=frozenset({
    ("POST", "/purchases"),
    ("POST", "/purchases/{pid}"),
    ("POST", "/supplies"),
    ("POST", "/supplies/{sid}/use"),
    ("POST", "/supplies/{sid}/dose"),
    ("POST", "/supplies/categories"),
})


def test_597_six_source_candidates_still_block_global_enforcement():
    assert len(ROUTES)==6
    assert ROUTES <= readiness.BROWSER_WITNESS_CANDIDATES
    assert ROUTES <= set(gap.EVIDENCE_MODULES)
    assert {gap.EVIDENCE_MODULES[r] for r in ROUTES} == {
        "tests/browser/test_strict_csrf521.py"
    }
    report=readiness.report()
    assert report["missing_witness_source_routes"] == []
    assert report["route_count"] == 144
    assert report["global_enable_authorized"] is False
    assert report["strict_csrf_enforce_installed"] is False
    assert report["status"] == "BLOCKED_INCOMPLETE_RUNTIME_CLEARANCE"
    plan=gap.build()
    assert plan["source_witness_candidates"] == 83
    assert plan["remaining_without_source_witness"] == 61
    assert len(plan["source_witness_manifest"]) == 70
    assert plan["runtime_verified_by_this_report"] is False
    assert plan["strict_csrf_enforcement_change_authorized"] is False
    assert any(row["path"].startswith("/purchases/")
               for row in plan["unqualified_routes"])


def test_597_browser_real_signed_purchases_and_usage_contracts():
    source=(ROOT/"tests/browser/test_strict_csrf521.py").read_text()
    ast.parse(source)
    marker="def test_597_purchase_and_supply_inventory_signed("
    assert source.count(marker)==1
    before, body=source.split(marker,1)
    assert '@pytest.mark.parametrize("scheme", ("http", "https"))' in before[-140:]
    assert "with page.expect_response(lambda response:" in body
    assert 'response.request.all_headers().get("x-tracker-csrf") == token' in body
    assert 'response.headers.get("x-tracker-csrf-report") == "valid"' in body
    assert 'response.status == 403' in body
    assert 'database.is_file() and not database.is_symlink()' in body
    assert 'DATA.parent.parent == Path("/tmp").resolve()' in body
    assert 'label="QA"+uuid4().hex[:12]+" supply category 597"' in body
    for path in (
        'create="/purchases"',
        'update=f"/purchases/{pid}"',
        'category="/supplies/categories"',
        'create_supply="/supplies"',
        'use=f"/supplies/{sid}/use"',
        'dose=f"/supplies/{pill_id}/dose"',
    ):
        assert path in body, path
    for table in ("purchases", "supply_categories", "supplies", "supply_usages"):
        assert table in body

    runner=(ROOT/"scripts/tracker-browser-qualify.sh").read_text()
    assert runner.count("-n 4 --dist=loadfile")==3
    _,strict=runner.split("# Release 521: a second browser gate",1)
    assert strict.count("tests/browser/test_strict_csrf521.py")==1
    assert runner.count("ISOLATED_STRICT_CSRF_BROWSER=PASSED")==1
