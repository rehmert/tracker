"""Stock review batch regressions."""

from pathlib import Path
from app.templating import templates

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text()


def test_controls():
    html = read("app/templates/supplies.html")
    for marker in (
        "data-stock-sort",
        "data-stock-breakdown",
        'value="attention"',
        'value="product"',
        'value="category"',
        'value="remaining-asc"',
        'value="remaining-desc"',
        'id="tracker-stock-section"',
    ):
        assert marker in html


def test_usage_forms_unchanged():
    html = read("app/templates/supplies.html")
    assert 'name="submission_token"' in html
    assert 'name="quantity"' in html
    assert "data-tracker-supply-use" in html


def test_csv_format():
    js = read("app/static/js/tracker-stock-filters.js")
    assert r"'\uFEFF'" in js
    assert r"'\r\n'" in js
    assert r"/[\r\n\t]+/g" in js
    assert r"'\\uFEFF'" not in js
    assert r"'\\r\\n'" not in js


def test_sort_and_export():
    js = read("app/static/js/tracker-stock-filters.js")
    for marker in (
        "function sortRows()",
        "originalOrder",
        "rows.sort(",
        "rows.filter(",
        "row.hidden = !show",
        "matching.available",
        "matching.low",
        "matching.depleted",
        "tbody.append(row)",
    ):
        assert marker in js


def test_print_scoped():
    js = read("app/static/js/tracker-stock-filters.js")
    css = read("app/static/css/tracker-stock-filters.css")
    assert "tracker-stock-print-mode" in js
    assert "afterprint" in js
    assert "window.print()" in js
    assert "#tracker-stock-section" in css


def test_no_inventory_write_api():
    js = read("app/static/js/tracker-stock-filters.js")
    for forbidden in (
        "fetch(",
        "XMLHttpRequest",
        "localStorage",
        "sessionStorage",
        "requestSubmit(",
        ".submit(",
    ):
        assert forbidden not in js


def test_template_parses():
    templates.env.get_template("supplies.html")
