"""Read-only Supplies stock filtering tests."""

from pathlib import Path

from app.templating import templates

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text()


def test_filter_assets_and_markup():
    html = read("app/templates/supplies.html")

    for token in (
        "tracker-stock-filters.js",
        "tracker-stock-filters.css",
        "data-stock-filter-toolbar",
        "data-stock-search",
        "data-stock-status-filter",
        "data-stock-filter-reset",
        "data-stock-visible-count",
        "data-stock-review-table",
        "data-stock-review-row",
        'data-stock-quick-filter="attention"',
    ):
        assert token in html


def test_original_inventory_controls_retained():
    html = read("app/templates/supplies.html")

    for token in (
        "data-stock-health-summary",
        "data-tracker-supply-use",
        'name="submission_token"',
        'name="quantity"',
        'data-remaining="{{ s.remaining_qty }}"',
        'data-enhanced-table',
    ):
        assert token in html


def test_filter_is_read_only():
    js = read(
        "app/static/js/tracker-stock-filters.js"
    )

    assert "row.hidden = !show" in js
    assert "rowSearchText" in js
    assert "data-stock-state" in js
    assert "Showing " in js

    for forbidden in (
        "fetch(",
        "XMLHttpRequest",
        "localStorage",
        "sessionStorage",
        ".submit(",
        "requestSubmit(",
    ):
        assert forbidden not in js


def test_accessibility_and_layout():
    html = read("app/templates/supplies.html")
    css = read(
        "app/static/css/tracker-stock-filters.css"
    )

    assert 'aria-live="polite"' in html
    assert "type=\"search\"" in html
    assert ":focus-visible" in css
    assert "@media print" in css
    assert "max-width: 760px" in css


def test_template_parses():
    templates.env.get_template("supplies.html")
