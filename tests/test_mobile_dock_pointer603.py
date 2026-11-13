"""Chromium regression: fixed mobile dock must not swallow blur-to-button clicks.

Loads actual Tracker JS files with a disposable page. No backend or inventory
writes are involved; works as an independent, fast targeted preflight.
"""
import os
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]

HTML = """<!doctype html><html><head><style>
body {margin:0;font:16px Arial}
.tracker-mobile-dock {
  position:fixed;bottom:0;left:0;right:0;height:90px;
  z-index:9999;background:#ddd;display:block;
}
.tracker-mobile-editing .tracker-mobile-dock {display:none}
.scroll {overflow-x:auto}
</style></head><body>
<div id="app-shell">
  <nav class="tracker-mobile-dock"><button id="tracker-mobile-more"
    type="button">More</button></nav>
  <button id="sidebar-open" type="button" hidden>Open</button>
  <main><div id="qa-spacer" style="height:690px"></div>
    <section id="purchase-history">
      <div data-purchase-review-toolbar>
        <input id="qa-search" data-purchase-search type="search">
        <button type="button" data-purchase-reset>Reset</button>
        <details data-mobile-optional603 class="purchase-review-more603" open>
          <summary>Dates &amp; export
            <span data-purchase-date-active603 hidden>Active</span>
          </summary>
          <input type="date" data-purchase-from>
          <input type="date" data-purchase-through>
        </details>
      </div>
      <div class="scroll"><table id="purchase-history-table"
        data-purchase-history><tbody>
        <tr data-purchase-row><td>2026-11-13</td><td>Vendor</td>
        <td>Order</td><td>0</td><td>2</td><td>12.25</td>
        <td><a href="#purchase-history">Review</a></td></tr>
      </tbody></table></div>
    </section>
    <form><details data-mobile-optional603 open>
      <summary>Optional fields</summary><input name="notes">
    </details></form>
    <div style="height:480px"></div>
  </main>
</div>
<script>document.querySelector('[data-purchase-reset]').addEventListener(
  'click', () => document.getElementById('qa-search').focus()
)</script>
</body></html>"""


@pytest.mark.parametrize("width", [320, 390, 430])
def test_click_above_dock_survives_search_blur(width):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None,
        )
        try:
            page = browser.new_page(viewport={"width": width, "height": 844})
            page.set_default_timeout(4000)
            errors = []
            page.on("pageerror", lambda err: errors.append(str(err)))
            page.set_content(HTML)
            page.add_script_tag(
                path=str(ROOT / "app/static/js/tracker-mobile-shell507.js")
            )
            page.add_script_tag(
                path=str(ROOT / "app/static/js/tracker-purchase-mobile603.js")
            )
            toggle = page.locator(".tracker-purchase-mobile-controls603 button")
            table = page.locator("#purchase-history-table")
            expect(toggle).to_have_text("Full sortable table")

            # Position the button inside the dock's eventual hit region.
            box = toggle.bounding_box()
            assert box
            delta = 782 - (box["y"] + box["height"] / 2)
            page.locator("#qa-spacer").evaluate(
                "(el, delta) => {el.style.height = (el.offsetHeight + delta) + 'px'}",
                delta,
            )
            page.locator("[data-purchase-reset]").click()
            expect(page.locator("#qa-search")).to_be_focused()
            assert page.evaluate(
                "getComputedStyle(document.querySelector('.tracker-mobile-dock')).display"
            ) == "none"

            # This native pointer click was swallowed by the dock before fix.
            toggle.click()
            expect(toggle).to_have_text("Card view")
            expect(toggle).to_have_attribute("aria-pressed", "false")
            expect(table).not_to_have_class("tracker-purchase-cards603")
            page.wait_for_function(
                "getComputedStyle(document.querySelector('.tracker-mobile-dock')).display !== 'none'"
            )
            # The dock must not return over the just-tapped control.
            assert toggle.evaluate("""el => {
                const dock = document.querySelector('.tracker-mobile-dock');
                return el.getBoundingClientRect().bottom <=
                    dock.getBoundingClientRect().top - 10;
            }""")

            # Reverse direction without manually scrolling or forcing a tap.
            toggle.click()
            expect(toggle).to_have_text("Full sortable table")
            expect(toggle).to_have_attribute("aria-pressed", "true")
            expect(table).to_have_class("tracker-purchase-cards603")
            assert not errors, errors
        finally:
            browser.close()
