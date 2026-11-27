"""Release 805: disclosure-aware page navigation and stable section links."""
from pathlib import Path
import os
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]


def test_805_cache_versions():
    base = (ROOT / "app/templates/base.html").read_text()
    assert base.count("tracker-page-navigation.js?v=805") == 1
    assert base.count("tracker-section-deep-links.js?v=805") == 1


def test_805_disclosure_navigation():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None)
        try:
            page = browser.new_page(viewport={"width": 390, "height": 800}, reduced_motion="reduce")
            page.route("**/*", lambda route: route.abort())
            page.set_content("""<main id="main-content"><div id="tracker-page-jump-slot"></div>
                <h2 id="existing">First</h2><h2>Second</h2><h2>Third</h2>
                <details id="outer"><summary>Advanced</summary><h2>Fourth</h2>
                <details id="inner" open><summary>Nested</summary><h3>Fifth</h3></details>
                </details></main>""")
            for file in ("tracker-page-navigation.js", "tracker-section-deep-links.js"):
                page.add_script_tag(content=(ROOT / "app/static/js" / file).read_text())
            options = page.locator("#tracker-page-jump-select option")
            expect(options).to_have_count(4)
            page.locator("#outer > summary").click()
            expect(options).to_have_count(6)
            expect(page.locator("#tracker-heading-fifth")).to_have_count(1)
            page.locator("#inner > summary").click()
            expect(options).to_have_count(5)
            page.locator("#outer > summary").click()
            expect(options).to_have_count(4)
            page.locator("#outer > summary").click()
            page.locator("#inner > summary").click()
            expect(options).to_have_count(6)
            expect(page.locator("#tracker-heading-fifth")).to_have_count(1)
            expect(page.locator("#existing")).to_have_count(1)
            page.evaluate("""() => {
                document.querySelector('#main-content').insertAdjacentHTML('beforeend', '<h2>New section</h2>');
                document.dispatchEvent(new Event('htmx:afterSwap'));
                document.dispatchEvent(new Event('htmx:afterSettle'));
            }""")
            expect(options).to_have_count(7)
            expect(page.locator("#tracker-heading-new-section")).to_have_count(1)
        finally:
            browser.close()
