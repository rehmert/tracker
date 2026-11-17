"""Disposable Chromium checks for Release 673 mobile spacing and actions.

No live application, real health data, network, backend, or writes required.
"""
import os
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
STYLES = ROOT / "app/static/css"

HTML = """<!doctype html><html><head><meta name="viewport"
content="width=device-width,initial-scale=1"></head><body>
<main id="main-content" style="max-width:100%;padding:8px;box-sizing:border-box">
<nav class="ux673-action-row"><button>Save</button><a class="btn" href="#done">Cancel</a></nav>
<div class="scroll"><table class="ux673-card-table">
<thead><tr><th>Product</th><th>Type</th><th>Remaining</th><th>Status</th></tr></thead>
<tbody><tr><td data-label="Product" data-ux673-full>Example inventory item with a long name</td>
<td data-label="Type">Syringes</td><td data-label="Remaining">20 units</td>
<td data-label="Status" data-ux673-action><button>Record use</button></td></tr>
</tbody></table></div>
<details class="ux673-food-more"><summary>More Food Tools &amp; Analysis</summary>
<nav><a href="#more">Saved Foods</a></nav></details>
<details class="ux673-gym-offline"><summary>Offline &amp; Draft Tools</summary>
<div class="ux673-gym-offline-content"><button>Restore Draft</button></div></details>
<div id="done"></div>
</main>
<nav class="tracker-mobile-dock" aria-label="Mobile quick navigation">
<a href="#done"><span>Home</span></a><a href="#done"><span>Today</span></a>
<a href="#done"><span>Log</span></a><a href="#done"><span>Workout</span></a>
<button type="button"><span>More</span></button></nav>
</body></html>"""


@pytest.mark.parametrize("width", [320, 390, 430])
def test_673_mobile_cards_dock_and_advanced_sections_fit(width):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None,
        )
        try:
            page = browser.new_page(viewport={"width": width, "height": 844})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.set_content(HTML)
            for file in ("tracker-mobile-shell507.css",
                         "tracker-mobile-ux673.css",
                         "tracker-food-ux673.css",
                         "tracker-workout-ux673.css"):
                page.add_style_tag(path=str(STYLES / file))
            assert page.locator(".tracker-mobile-dock > *").count() == 5
            assert page.locator("table.ux673-card-table tbody tr").evaluate(
                "el => getComputedStyle(el).display"
            ) == "grid"
            assert page.locator("table.ux673-card-table thead").evaluate(
                "el => getComputedStyle(el).display"
            ) == "none"
            assert page.evaluate(
                "() => document.documentElement.scrollWidth <= window.innerWidth + 1"
            )
            for selector in (".ux673-action-row button",
                             ".tracker-mobile-dock button",
                             'td[data-ux673-action] button'):
                assert page.locator(selector).first.evaluate(
                    "el => el.getBoundingClientRect().height >= 44"
                ), selector
            food = page.locator(".ux673-food-more")
            gym = page.locator(".ux673-gym-offline")
            assert not food.evaluate("el => el.open")
            assert not gym.evaluate("el => el.open")
            food.locator("summary").click()
            gym.locator("summary").click()
            assert food.evaluate("el => el.open")
            assert gym.evaluate("el => el.open")
            assert not errors, errors
        finally:
            browser.close()
