"""Browser checks for date preset/custom synchronization (isolated HTML)."""
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

pytestmark = pytest.mark.browser
ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "app/static/js/tracker-health-timeline-dates.js"


@pytest.fixture
def page():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        tab = browser.new_page()
        errors = []
        tab.on("pageerror", lambda error: errors.append(str(error)))
        tab.set_content("""<!doctype html><html><body>
          <form id="health-timeline-filters" method="get">
            <select name="days" id="timeline-days">
              <option value="7">7 days</option>
              <option value="30">30 days</option>
              <option value="90" selected>90 days</option>
              <option value="180">6 months</option>
              <option value="365">1 year</option>
              <option value="3650">All</option>
              <option value="0">Custom dates</option>
            </select>
            <input type="date" name="start_date" id="timeline-from">
            <input type="date" name="end_date" id="timeline-through">
          </form>
        </body></html>""")
        tab.add_script_tag(path=str(SCRIPT))
        yield tab, errors
        browser.close()


def test_custom_date_fields_select_custom_range(page):
    tab, errors = page
    tab.locator("#timeline-from").fill("2026-10-15")
    assert tab.locator("#timeline-days").input_value() == "0"
    tab.locator("#timeline-through").fill("2026-10-31")
    assert tab.locator("#timeline-days").input_value() == "0"
    assert not errors, errors


def test_preset_switch_resets_stale_custom_dates(page):
    tab, errors = page
    tab.locator("#timeline-from").fill("2026-10-15")
    tab.locator("#timeline-through").fill("2026-10-31")
    tab.locator("#timeline-days").select_option("30")
    assert tab.locator("#timeline-from").input_value() == ""
    assert tab.locator("#timeline-through").input_value() == ""
    assert tab.locator("#timeline-days").input_value() == "30"
    assert not errors, errors
