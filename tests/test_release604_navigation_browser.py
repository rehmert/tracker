"""Isolated Chromium check for Release 604 navigation simplification.

Loads exact navigation template fragments and actual CSS/JS. No server, login,
records, network requests, or database writes.
"""
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
QUICK = (ROOT / "app/templates/quick_entry.html").read_text(encoding="utf-8")
VIALS = (ROOT / "app/templates/vials.html").read_text(encoding="utf-8")
QUICK_CSS = (
    (ROOT / "app/static/css/tracker-quick-entry.css").read_text()
    + "\n" +
    (ROOT / "app/static/css/tracker-mobile-daily602.css").read_text()
    + "\n" +
    (ROOT / "app/static/css/tracker-navigation604.css").read_text()
)
VIAL_CSS = (ROOT / "app/static/css/tracker-inventory-mobile603.css").read_text()


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        instance = p.chromium.launch(headless=True)
        try:
            yield instance
        finally:
            instance.close()


def fixture_page(browser, width, content, css):
    page = browser.new_page(viewport={"width": width, "height": 844})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.set_content(
        '<!doctype html><html><head><meta name="viewport" '
        'content="width=device-width,initial-scale=1">'
        '<style>' + css + '</style></head><body><main>'
        + content + '</main></body></html>'
    )
    return page, errors


@pytest.mark.parametrize("width", [320, 390, 1024])
def test_604_quick_entry_shortcuts_disclose_without_losing_links(browser, width):
    start = QUICK.index('<nav class="tracker-quick-fast-paths"')
    end = QUICK.index("</nav>", start) + len("</nav>")
    page, errors = fixture_page(browser, width, QUICK[start:end], QUICK_CSS)
    try:
        nav = page.locator("nav.tracker-quick-fast-paths")
        all_links = nav.locator("a")
        assert all_links.count() == 15
        primary = nav.locator(".tracker-quick-fast-primary604 a")
        extra = nav.locator(".tracker-quick-fast-secondary604 a")
        assert primary.count() == 6
        assert extra.count() == 9
        if width <= 760:
            assert nav.locator(".tracker-quick-fast-primary604").evaluate(
                """el => getComputedStyle(el).overflowX === 'auto'
                   && el.scrollWidth > el.clientWidth"""
            ), "Expected genuine swipeable primary shortcut row"
        for link in primary.all():
            expect(link).to_be_visible()
        for link in extra.all():
            expect(link).to_be_hidden()
        disclosure = nav.locator("details.tracker-quick-fast-more604")
        summary = disclosure.locator("summary")
        expect(summary).to_be_visible()
        expect(summary).to_have_text("More direct shortcuts")
        summary.focus()
        summary.press("Enter")
        expect(disclosure).to_have_attribute("open", "")
        for link in extra.all():
            expect(link).to_be_visible()
        assert nav.locator('a[href="/labs/new#lab-csv-entry"]').count() == 1
        summary.press("Enter")
        expect(disclosure).not_to_have_attribute("open", "")
        assert not errors, errors
    finally:
        page.close()


@pytest.mark.parametrize("width", [320, 390, 1024])
def test_604_vials_single_navigation_keeps_original_destinations(browser, width):
    start = VIALS.index('<nav class="tracker-vial-jumps603"')
    end = VIALS.index("</nav>", start) + len("</nav>")
    html = (VIALS[start:end] +
            '<section id="tracker-vials-sortable">Inventory</section>'
            '<div id="tracker-vial-find-panel">Search</div>'
            '<div id="bulk-selection-toolbar">Selection</div>'
            '<details id="tracker-inventory-reports">'
            '<summary>Reports</summary><p>Reports body</p></details>'
            '<section id="tracker-vial-lifecycle">Lifecycle</section>')
    page, errors = fixture_page(browser, width, html, VIAL_CSS)
    try:
        page.add_script_tag(
            path=str(ROOT / "app/static/js/tracker-vial-jumps603.js")
        )
        nav = page.locator(".tracker-vial-jumps603")
        assert nav.count() == 1
        assert nav.locator("a").count() == 9
        report = page.locator("#tracker-inventory-reports")
        expect(report).not_to_have_attribute("open", "")
        nav.locator('a[href="#tracker-inventory-reports"]').click()
        expect(report).to_have_attribute("open", "")
        for route in (
            "/inventory-intelligence", "/inventory-alerts", "/reconciliation"
        ):
            assert nav.locator(f'a[href="{route}"]').count() == 1
        assert not errors, errors
    finally:
        page.close()
