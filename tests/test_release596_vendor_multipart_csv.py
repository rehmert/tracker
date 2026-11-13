"""Release 596: conservative source-only vendor upload and CSV witnesses."""
from __future__ import annotations

import ast
from pathlib import Path

from scripts import tracker_csrf_readiness588 as readiness
from scripts import tracker_csrf_gap_plan590 as gap

ROOT = Path(__file__).resolve().parents[1]
ROUTES = frozenset({
    ("POST", "/vendor-prices/attachments/upload"),
    ("POST", "/vendor-prices/attachments/{attachment_id}/delete"),
    ("POST", "/vendor-prices/items-csv/preview"),
    ("POST", "/vendor-prices/items-csv/save"),
    ("POST", "/vendor-prices/bulk/preview"),
    ("POST", "/vendor-prices/bulk/save"),
    ("POST", "/vendor-prices/preview"),
})


def test_596_exact_source_witness_manifest_and_no_global_clearance():
    assert len(ROUTES) == 7
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


def test_596_browser_signed_multipart_and_csv_import_coverage():
    source = (ROOT / "tests/browser/test_strict_csrf521.py").read_text()
    ast.parse(source)
    marker = "def test_596_vendor_multipart_and_csv_roundtrip_signed("
    assert source.count(marker) == 1
    head, body = source.split(marker, 1)
    assert '@pytest.mark.parametrize("scheme", ("http", "https"))' in head[-140:]
    assert "with page.expect_response(lambda response:" in body
    assert 'response.request.all_headers().get("x-tracker-csrf") == token' in body
    assert 'response.headers.get("x-tracker-csrf-report") == "valid"' in body
    assert "response.status == 403" in body
    assert "new FormData()" in body and "new File(" in body
    assert "new URLSearchParams(fields)" in body
    assert 'DATA.parent.parent == Path("/tmp").resolve()' in body
    assert "database.is_file() and not database.is_symlink()" in body
    # Preview fixtures must not collide between parallel HTTP/HTTPS cases.
    assert 'structured_item = "QA structured 596 " + uuid4().hex[:8]' in body
    assert 'bulk_item = "QA bulk 596 " + uuid4().hex[:8]' in body
    assert 'legacy_item = "QA legacy 596 " + uuid4().hex[:8]' in body
    assert "new DOMParser().parseFromString(html,'text/html')" in body
    assert "'textarea[name=\"review_text\"]'" in body
    assert 'Item,Strength,Package,Vials,Price' in body
    assert "download.body() == saved_bytes" in body
    for endpoint in (
        "/vendor-prices/attachments/upload",
        "/vendor-prices/attachments/{attachment_id}/delete",
        "/vendor-prices/items-csv/preview",
        "/vendor-prices/items-csv/save",
        "/vendor-prices/bulk/preview",
        "/vendor-prices/bulk/save",
        "/vendor-prices/preview",
    ):
        assert endpoint.split("{")[0] in body, endpoint
    for table in (
        "vendor_price_attachments",
        "vendor_price_entries",
        "vendor_price_sheets",
    ):
        assert table in body

    runner = (ROOT / "scripts/tracker-browser-qualify.sh").read_text()
    _, strict = runner.split("# Release 521: a second browser gate", 1)
    assert strict.count("tests/browser/test_strict_csrf521.py") == 1
    assert runner.count("-n 4 --dist=loadfile") == 3
    assert runner.count("ISOLATED_STRICT_CSRF_BROWSER=PASSED") == 1
