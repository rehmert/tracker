"""Browser regressions for batched layout and selective title observation."""
from pathlib import Path
import os
import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1] / "app/static"

@pytest.fixture
def page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None)
        try:
            page = browser.new_page(viewport={"width": 390, "height": 800})
            page.route("**/*", lambda route: route.abort())
            yield page
        finally:
            browser.close()

def test_explanations_preserve_expansion_and_resize(page):
    page.set_content('<main><section><h2>Heading</h2><p class="note">Short</p><p class="note">' + 'Long explanation ' * 12 + '</p></section></main>')
    page.add_style_tag(content=(ROOT / "css/tracker-section-explanations598.css").read_text())
    page.add_script_tag(content=(ROOT / "js/tracker-section-explanations598.js").read_text())
    buttons = page.locator(".tracker-explanation598-toggle")
    buttons.nth(1).wait_for(state="visible")
    assert not buttons.nth(0).is_visible()
    buttons.nth(1).click()
    assert buttons.nth(1).get_attribute("aria-expanded") == "true"
    page.set_viewport_size({"width": 1440, "height": 800})
    assert buttons.nth(1).is_visible()
    buttons.nth(1).click()
    assert buttons.nth(1).get_attribute("aria-expanded") == "false"

def test_title_observer_ignores_unrelated_changes_and_formats_new_headings(page):
    page.set_content('<main id="main-content"><h1>first heading</h1><h2>customCompound title</h2><div id="rows"></div></main>')
    page.evaluate("""() => {
      window.fetch = async () => ({ok:true,json:async()=>({names:['customCompound']})});
      window.scans = 0;
      const main = document.querySelector('main');
      const original = main.querySelectorAll.bind(main);
      main.querySelectorAll = (...args) => {window.scans++; return original(...args);};
    }""")
    page.add_script_tag(content=(ROOT / "js/tracker-page-title-case.js").read_text())
    page.wait_for_function("document.querySelector('h1').textContent === 'First Heading'")
    page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
    before = page.evaluate("window.scans")
    page.evaluate("document.querySelector('#rows').innerHTML = '<p>unrelated row</p>'")
    page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
    assert page.evaluate("window.scans") == before
    page.evaluate("document.querySelector('#rows').innerHTML = '<h3>new heading</h3>'")
    page.wait_for_function("document.querySelector('h3').textContent === 'New Heading'")
    assert page.locator("h2").inner_text() == "customCompound title"
    page.evaluate("document.querySelector('h3').firstChild.nodeValue = 'edited heading'")
    page.wait_for_function("document.querySelector('h3').textContent === 'Edited Heading'")
