"""Release 696: isolated Chromium for combined daily and inventory UX."""
import os
from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
BASE_URL = os.environ.get("TRACKER_TEST_URL", "").rstrip("/")
pytestmark = pytest.mark.skipif(
    os.environ.get("TRACKER_TEST_ISOLATED") != "1",
    reason="Only run Release 696 browsers against the disposable candidate server",
)


@pytest.mark.parametrize("width", (320, 390, 1280))
def test_696_integrated_navigation_and_page_order(width):
    assert BASE_URL.startswith("http://127.0.0.1:")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None,
        )
        try:
            page = browser.new_page(viewport={"width": width, "height": 850})
            problems = []
            page.on("pageerror", lambda err: problems.append(str(err)))
            for url in ("/vials", "/purchases", "/coas", "/labs"):
                response = page.goto(BASE_URL + url, wait_until="networkidle")
                assert response is not None and response.status == 200, url
                expect(page.locator('link[href="/static/css/tracker-integrated-flow696.css?v=696"]')).to_have_count(1)
                if url == "/vials":
                    nav = page.locator(".tracker-vial-jumps603")
                    expect(nav.locator("a")).to_have_count(9)
                    more = nav.locator("details.tracker-flow696-more")
                    more.locator("summary").click()
                    expect(more).to_have_attribute("open", "")
                    expect(more.get_by_role("link", name="Reconcile")).to_be_visible()
                    if width <= 760:
                        assert nav.evaluate(
                            "el => getComputedStyle(el).overflowX === 'visible'"
                        )
                elif url == "/purchases":
                    positions = page.evaluate("""() => ({
                        newOrder: document.querySelector('#new-purchase').compareDocumentPosition(
                            document.querySelector('#purchase-history')
                        ),
                        form: document.querySelectorAll('form[action="/purchases"]').length
                    })""")
                    # DOCUMENT_POSITION_FOLLOWING is bit 4.
                    assert positions["newOrder"] & 4, positions
                    assert positions["form"] == 1
                elif url == "/coas":
                    search = page.locator("[data-flow696-search]")
                    expect(search).to_be_visible()
                    expect(page.locator("[data-flow696-count]")).to_contain_text("certificates")
                    expect(page.get_by_role("link", name="+ Add COA")).to_be_visible()
                elif url == "/labs":
                    expect(page.locator("#labs-reports-section")).to_be_visible()
                    assert page.evaluate("""() => {
                      const reports=document.querySelector('#labs-reports-section');
                      const trends=document.querySelector('#lab-trends-section');
                      return !trends || Boolean(reports.compareDocumentPosition(trends)&4);
                    }""")
            assert not problems, problems
        finally:
            browser.close()


def test_696_coa_local_search_only_filters_visible_rows():
    js = (ROOT / "app/static/js/tracker-coa-find696.js").read_text(encoding="utf-8")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None,
        )
        try:
            page = browser.new_page(viewport={"width": 390, "height": 800})
            page.set_content("""<!doctype html><html><body>
              <section data-flow696-coas>
                <input type="search" data-flow696-search>
                <button type="button" data-flow696-reset>Clear</button>
                <p data-flow696-count role="status"></p>
                <p data-flow696-empty hidden>No results</p>
                <table><tbody>
                  <tr data-flow696-coa-row><td>Alpha</td><td>Janoshik</td></tr>
                  <tr data-flow696-coa-row><td>Beta</td><td>Second Lab</td></tr>
                </tbody></table>
              </section>
            </body></html>""")
            page.add_script_tag(content=js)
            input_box = page.locator("[data-flow696-search]")
            expect(page.locator("[data-flow696-count]")).to_have_text("Showing 2 of 2 certificates")
            input_box.fill("janoshik")
            expect(page.locator("[data-flow696-coa-row]:visible")).to_have_count(1)
            expect(page.locator("[data-flow696-coa-row]:visible")).to_contain_text("Alpha")
            input_box.fill("not here")
            expect(page.locator("[data-flow696-coa-row]:visible")).to_have_count(0)
            expect(page.locator("[data-flow696-empty]")).to_be_visible()
            page.locator("[data-flow696-reset]").click()
            expect(page.locator("[data-flow696-coa-row]:visible")).to_have_count(2)
            expect(page.locator("[data-flow696-empty]")).to_be_hidden()
        finally:
            browser.close()


@pytest.mark.parametrize("path,anchor", (
    ("/food", "#food-quick-log"),
    ("/doses", "#dose-history"),
    ("/vitals", "#quick-vitals-entry"),
))
@pytest.mark.parametrize("width", (390, 1280))
def test_696_daily_entry_guidance_is_optional_and_original_targets_remain(path, anchor, width):
    assert BASE_URL.startswith("http://127.0.0.1:")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None,
        )
        try:
            page = browser.new_page(viewport={"width":width,"height":850})
            response = page.goto(BASE_URL + path, wait_until="networkidle")
            assert response is not None and response.status == 200, path
            guide = page.locator("details.tracker-flow696-guide").first
            expect(guide.locator("summary")).to_be_visible()
            assert not guide.evaluate("el => el.open")
            assert page.locator(anchor).count() == 1
            assert guide.locator("summary").evaluate(
                "el => el.getBoundingClientRect().height >= 44"
            )
            guide.locator("summary").click()
            assert guide.evaluate("el => el.open")
            expect(guide).to_be_visible()
        finally:
            browser.close()
