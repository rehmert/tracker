"""Release 676: Chromium checks for *computed* shortcut-button styling."""
from pathlib import Path
import os
import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
CSS_675 = (ROOT / "app/static/css/tracker-action-nav675.css").read_text()
CSS_676 = (ROOT / "app/static/css/tracker-shortcut-buttons676.css").read_text()
CSS_DAILY = (ROOT / "app/static/css/tracker-mobile-daily509.css").read_text()
DOC = """<!doctype html><html><head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
:root{--surface:#fff;--rule:#cbd5e1;--ink:#192c31;--teal:#1265ad;--teal-ink:#fff;--wash:#f1f5f9}
*{box-sizing:border-box}body{margin:0;font:16px system-ui}main{padding:10px}
</style></head><body><main id="main-content">
<nav class="tracker-daily-actions"><a href="#daily">Daily Reference</a>
<a class="tracker-daily-action-primary" href="#daily-primary">Log Vitals</a></nav>
<nav class="ux675-actions" aria-label="Workout shortcuts">
<a class="ux675-primary" href="#gym">Gym Mode</a><a href="#progress">Progress</a>
<a href="#calendar">Calendar</a>
<details class="ux675-more"><summary>More</summary>
<div><a href="#history">Log Past Workout</a><a href="#insights">Insights</a></div>
</details></nav>
<a class="ux675-inline-action" href="#history">Machine History</a>
</main></body></html>"""


@pytest.mark.parametrize("width", (320, 375, 390, 430, 768))
def test_676_mobile_links_look_like_daily_shortcut_tiles(width):
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None,
        )
        try:
            page = browser.new_page(viewport={"width":width,"height":800})
            page.set_content(DOC)
            page.add_style_tag(content=CSS_DAILY + "\n" + CSS_675 + "\n" + CSS_676)
            css = lambda selector: page.locator(selector).evaluate(
                """el => {
                    const s=getComputedStyle(el), b=el.getBoundingClientRect();
                    return {background:s.backgroundColor,color:s.color,weight:s.fontWeight,
                            radius:s.borderRadius,border:s.borderTopStyle,
                            display:s.display,height:b.height,width:b.width}
                }"""
            )
            reference = css(".tracker-daily-actions a:not(.tracker-daily-action-primary)")
            primary_ref = css(".tracker-daily-action-primary")
            normal = css('.ux675-actions > a[href="#progress"]')
            primary = css(".ux675-actions > a.ux675-primary")
            summary = css(".ux675-more > summary")
            inline = css(".ux675-inline-action")
            for cell in (normal, summary, inline):
                assert cell["background"] == reference["background"], (cell, reference)
                assert cell["weight"] == reference["weight"]
                assert cell["radius"] == reference["radius"]
                assert cell["border"] == "solid"
                assert cell["height"] >= 44
            assert primary["background"] == primary_ref["background"]
            assert primary["color"] == primary_ref["color"]
            assert primary["height"] >= 44
            assert page.locator(".ux675-actions").evaluate(
                "el => getComputedStyle(el).display"
            ) == "grid"
            assert page.evaluate(
                "() => document.documentElement.scrollWidth <= innerWidth + 1"
            )
            page.locator(".ux675-more > summary").click()
            assert page.locator(".ux675-more").evaluate("el => el.open")
            nested = css('.ux675-more > div > a:first-child')
            assert nested["background"] == reference["background"]
            assert nested["height"] >= 44
            assert page.evaluate(
                "() => document.documentElement.scrollWidth <= innerWidth + 1"
            )
        finally:
            browser.close()
