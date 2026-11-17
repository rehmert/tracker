"""Release 675 disposable mobile-Chromium action group check.

Tests the shipped CSS with static markup. No database or network writes.
"""
import os
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "app/static/css/tracker-action-nav675.css"

HTML = """<!doctype html><html><head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{box-sizing:border-box}
body{margin:0;font:16px system-ui, sans-serif}
main{padding:10px;max-width:100%;width:100%}
</style></head><body><main>
<nav class="ux675-actions" aria-label="Workout shortcuts">
<a class="ux675-primary" href="#gym">Gym Mode</a>
<a href="#progress">Progress</a>
<a href="#calendar">Calendar</a>
<details class="ux675-more"><summary>More</summary>
<div><a href="#history">Log Past Workout</a><a href="#insights">Insights</a>
<a href="#routines">Routines</a></div></details>
</nav>
<p><a class="ux675-inline-action" href="#history">Machine History</a></p>
<div id="gym"></div><div id="progress"></div><div id="calendar"></div>
<div id="history"></div><div id="insights"></div><div id="routines"></div>
</main></body></html>"""


@pytest.mark.parametrize("width", (320, 375, 390, 430, 768))
def test_675_mobile_action_targets_and_more_disclosure(width):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None,
        )
        try:
            page = browser.new_page(viewport={"width": width, "height": 844})
            failures = []
            page.on("pageerror", lambda err: failures.append(str(err)))
            page.set_content(HTML)
            page.add_style_tag(path=str(CSS))
            assert page.evaluate(
                "() => document.documentElement.scrollWidth <= window.innerWidth + 1"
            )
            for selector in (".ux675-actions > a", ".ux675-more > summary",
                             ".ux675-inline-action"):
                heights = page.locator(selector).evaluate_all(
                    "nodes => nodes.map(x => x.getBoundingClientRect().height)"
                )
                assert heights and all(height >= 44 for height in heights), (selector, heights)
            more = page.locator(".ux675-more")
            assert not more.evaluate("el => el.open")
            more.locator("summary").click()
            assert more.evaluate("el => el.open")
            assert page.locator('.ux675-more a[href="#history"]').is_visible()
            assert page.evaluate(
                "() => document.documentElement.scrollWidth <= window.innerWidth + 1"
            )
            assert not failures, failures
        finally:
            browser.close()
