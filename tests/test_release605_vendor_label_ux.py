"""Release 605: read-only Vendor Offer paging and individual label zoom.

The actual vendor sorting code and existing Release 449 label-zoom asset are
exercised in isolated Chromium. No API server, database, uploads or writes.
"""
from pathlib import Path
import re

import pytest
from jinja2 import Environment
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
VENDOR = (ROOT / "app/templates/vendor_prices.html").read_text(encoding="utf-8")
LABEL = (ROOT / "app/templates/vial_labels423.html").read_text(encoding="utf-8")
ZOOM = ROOT / "app/static/js/tracker-label-preview-zoom449.js"


def test_605_sources_keep_canonical_forms_exports_and_data():
    Environment().parse(VENDOR)
    Environment().parse(LABEL)
    for marker in (
        'id="vendor-offer-pager605"',
        'id="vendor-offer-page-size605"',
        'id="vendor-offer-prev605"',
        'id="vendor-offer-next605"',
        'id="vendor-offer-page-info605"',
        "Array.from(body.querySelectorAll('tr[data-offer-row]'))",
        "page = 0;\n    applyCompoundFilter();",
        "row.hidden = !visible",
        "rows.forEach(row => body.appendChild(row));",
        'action="/vendor-prices/manual"',
        'action="/vendor-prices/items-csv/preview"',
    ):
        assert marker in VENDOR, marker
    assert "cloneNode(" not in VENDOR
    assert "fetch(" not in _vendor_script()
    for marker in (
        'id="label-preview-zoom449"',
        '<option value="3" selected>300% (default)</option>',
        'class="single-label-preview-image605"',
        "zoom:var(--label-preview-scale)",
        "zoom:1!important",
        'tracker-label-preview-zoom449.js?v=449',
        '/vials/{{ v.id }}/labels/export?fmt=png',
        '/vials/{{ v.id }}/labels/export?fmt=svg',
    ):
        assert marker in LABEL, marker
    assert 'name="zoom"' not in LABEL
    assert '<form method="get" action="/vials/{{ v.id }}/labels"' in LABEL
    assert "window.print(" not in ZOOM.read_text()


def _vendor_script():
    match = re.search(
        r"<script>\s*(\(function \(\) \{.*?\}\)\(\);)\s*</script>",
        VENDOR, re.DOTALL
    )
    assert match, "Vendor table's actual inline script is required"
    return match.group(1)


def _offer_row(number):
    compound = "A" if number < 40 else "B"
    # Vendor names are reverse of initial row order, exposing real cross-page sort.
    cells = [
        f"<td>Compound {compound}</td>",
        '<td>10 mg</td>',
        f"<td>Vendor {60 - number:03d}</td>",
        '<td>Kit</td>',
        '<td data-sort="10">10</td>',
        f'<td data-sort="{number + 1}">${number + 1}</td>',
    ]
    cells.extend("<td>—</td>" for _ in range(3))
    cells.append(
        f'<td class="vendor-delivered-total" data-sort="{100 + number}">'
        f'${100 + number}</td>'
    )
    cells.extend("<td>—</td>" for _ in range(3))
    assert len(cells) == 13
    return (
        f'<tr data-offer-row data-compound="{compound}" data-strength="10mg" '
        f'data-vials="10" data-index="{number}">' + "".join(cells) + "</tr>"
    )


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        instance = p.chromium.launch(headless=True)
        try:
            yield instance
        finally:
            instance.close()


@pytest.mark.parametrize("width", [320, 390, 1024])
def test_605_vendor_paging_survives_filter_and_sort(browser, width):
    headers = "".join(
        f'<th><button type="button" data-sort-column="{col}">'
        f'Sort {col}<span class="vendor-sort-indicator">↕</span></button></th>'
        for col in (0, 2, 5)
    )
    markup = (
        '<select id="vendor-compound-filter"><option value="">All compounds</option></select>'
        '<p id="vendor-compound-count"></p>'
        '<div id="vendor-offer-pager605" hidden>'
        '<select id="vendor-offer-page-size605">'
        '<option value="25">25</option><option value="50">50</option>'
        '<option value="100">100</option><option value="all">All</option></select>'
        '<button id="vendor-offer-prev605">Previous</button>'
        '<span id="vendor-offer-page-info605"></span>'
        '<button id="vendor-offer-next605">Next</button></div>'
        f'<table id="vendor-offers-table"><thead><tr>{headers}</tr></thead>'
        f'<tbody>{"".join(_offer_row(i) for i in range(61))}</tbody></table>'
    )
    page = browser.new_page(viewport={"width": width, "height": 844})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.set_content(markup)
        page.add_script_tag(content=_vendor_script())
        visible = lambda: page.locator('tr[data-offer-row]:visible')
        assert visible().count() == 25
        assert visible().first.get_attribute("data-index") == "0"
        assert "1–25 of 61" in page.locator("#vendor-offer-page-info605").inner_text()

        page.locator("#vendor-offer-next605").click()
        assert visible().count() == 25
        assert visible().first.get_attribute("data-index") == "25"
        page.locator("#vendor-compound-filter").select_option("B")
        assert visible().count() == 21
        assert visible().first.get_attribute("data-index") == "40"
        assert page.locator("#vendor-offer-pager605").is_hidden()
        assert "21 of 61 offers match filter" in page.locator(
            "#vendor-compound-count"
        ).inner_text()

        page.locator("#vendor-compound-filter").select_option("A")
        assert visible().count() == 25
        assert page.locator("#vendor-offer-pager605").is_visible()
        # Sorting by vendor must consider all 40 matching rows, not just page 1.
        page.locator('button[data-sort-column="2"]').click()
        assert visible().first.get_attribute("data-index") == "39"
        page.locator("#vendor-offer-next605").click()
        assert visible().count() == 15
        page.locator("#vendor-offer-page-size605").select_option("all")
        assert visible().count() == 40
        assert page.locator("#vendor-offer-pager605").is_hidden()
        assert not errors, errors
    finally:
        page.close()


@pytest.mark.parametrize("width", [320, 390, 1024])
def test_605_single_label_zoom_defaults_and_changes_without_export(browser, width):
    start = LABEL.index('<div class="single-label-preview-controls605">')
    end = LABEL.index("</div>", start) + len("</div>")
    controls = LABEL[start:end]
    css = re.search(r"<style>(.*?)</style>", LABEL, re.DOTALL)
    assert css
    image = (
        '<div class="scroll single-label-preview-scroll605" style="width:280px">'
        '<img class="single-label-preview-image605" alt="Vial label preview" '
        'src="data:image/svg+xml,%3Csvg%20xmlns=%22http://www.w3.org/2000/svg%22%20width=%2240mm%22%20height=%2220mm%22/%3E"></div>'
    )
    page = browser.new_page(viewport={"width": width, "height": 844})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.set_content("<style>" + css.group(1) + "</style>" + controls + image)
        page.add_script_tag(path=str(ZOOM))
        zoom = page.locator("#label-preview-zoom449")
        img = page.locator(".single-label-preview-image605")
        assert zoom.input_value() == "3"
        assert img.evaluate("(el) => getComputedStyle(el).zoom") == "3"
        zoom.select_option("4")
        assert img.evaluate("(el) => getComputedStyle(el).zoom") == "4"
        assert "400%" in page.locator("#label-preview-zoom-status449").inner_text()
        assert page.locator(".single-label-preview-scroll605").evaluate(
            "(el) => el.scrollWidth > el.clientWidth"
        )
        assert not errors, errors
    finally:
        page.close()
