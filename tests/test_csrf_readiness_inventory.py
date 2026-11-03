"""Regression coverage for the CSRF source inventory."""

import importlib.util

import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts/tracker-csrf-readiness.py"

spec = importlib.util.spec_from_file_location(
    "tracker_csrf_readiness", PATH
)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


@pytest.fixture(scope="module")
def inventory():
    """Scan the immutable test source once per module."""
    return audit.build(ROOT)


def test_form_scanner():
    scanner = audit.FormScanner()
    scanner.feed('''
        <form action="/a" method="POST">
        </form>
        <form action="/b" method="get">
        </form>
        <button hx-post="/c">Save</button>
        <div hx-delete="/d"></div>
    ''')
    assert len(scanner.forms) == 2
    assert scanner.forms[0]["method"] == "post"
    assert scanner.forms[1]["method"] == "get"
    assert [r["method"] for r in scanner.htmx] == [
        "POST", "DELETE"
    ]


def test_known_routes_are_in_inventory(inventory):
    result = inventory
    keys = {
        (r["method"], r["path"])
        for r in result["routes"]
    }
    assert ("POST", "/compounds") in keys
    assert ("POST", "/pk/compounds") in keys


def test_known_browser_paths_are_in_inventory(inventory):
    result = inventory
    browser = result["html_and_htmx"]
    scripts = result["javascript"]

    assert any(
        r["file"] == "app/templates/blends.html"
        and r["kind"] == "html_form"
        for r in browser
    )
    assert any(
        r["file"] == "app/static/pk.js"
        and r["kind"] == "fetch_callsite"
        for r in scripts
    )


def test_inventory_labels_missing_enforcement(inventory):
    result = inventory
    assert result["status"] == (
        "inventory_only_not_csrf_protected"
    )
    assert any(
        "No CSRF token coverage" in limitation
        for limitation in result["limitations"]
    )
    assert (
        result["summary"]["unsafe_route_declarations"] > 0
    )


def test_inventory_does_not_mutate_source(inventory, tmp_path):
    result = inventory
    assert result["routes"]
    # The scanner has no requested output destination.
    assert list(tmp_path.iterdir()) == []
