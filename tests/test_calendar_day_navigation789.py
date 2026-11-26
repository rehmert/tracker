"""Exercise the actual calendar range, filter and matching-day scripts together."""
from pathlib import Path
import os

import pytest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app/static"
DATES = ("2026-11-23", "2026-11-24", "2026-11-25", "2026-11-26", "2026-11-27")
SCRIPTS = ("tracker-calendar-views374.js", "tracker-calendar-workbench.js",
           "tracker-calendar-day-context.js", "tracker-calendar-day-navigation.js")


@pytest.mark.parametrize("width", [390, 1280])
def test_789_day_navigation_keeps_visible_date_and_matching_controls_in_sync(width):
    days = "".join(
        f'<div class="calendar-day" id="calendar-day-{day}" data-calendar-date="{day}">'
        f'<strong>{day}</strong>'
        + (f'<div class="calendar-activity" data-calendar-status="due" '
           f'data-calendar-search="{("Alpha" if i % 2 == 0 else "Beta")}">Event</div>'
           if i != 1 else "") + "</div>"
        for i, day in enumerate(DATES)
    )
    html = """<!doctype html><meta name="viewport" content="width=device-width, initial-scale=1">
    <div id="calendar-workbench"><input id="calendar-search">
    <select id="calendar-status-filter"><option value="all">All</option></select>
    <button id="calendar-reset-filters">Reset</button><button id="calendar-print">Print</button>
    <p id="calendar-filter-summary"></p></div>
    <button id="calendar-previous-matching-day">Previous day</button>
    <button id="calendar-next-matching-day">Next day</button>
    <p id="calendar-matching-day-status"></p>
    <div class="calendar-grid" id="calendar-grid">""" + days + "</div>"
    html += '<style>' + (STATIC / "css/tracker-calendar-bundle742.css").read_text() + '</style>'
    html += "".join("<script>" + (STATIC / "js" / name).read_text() + "</script>" for name in SCRIPTS)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None)
        try:
            page = browser.new_page(viewport={"width": width, "height": 800})
            page.route("http://tracker.test/**", lambda route: route.fulfill(
                status=200, content_type="text/html", body=html))
            page.goto("http://tracker.test/calendar#calendar-day-2026-11-25")
            page.locator('[data-calendar-mode="day"]').click()

            def expect_day(day):
                from playwright.sync_api import expect
                expect(page.locator("#calendar-grid")).to_have_attribute("data-calendar-anchor", day)
                expect(page.locator(".calendar-day:visible")).to_have_count(1)
                expect(page.locator("#calendar-day-" + day)).to_be_visible()

            expect_day(DATES[2])
            page.locator("#calendar-next-matching-day").click()
            expect_day(DATES[3])
            page.locator("#calendar-previous-matching-day").click()
            expect_day(DATES[2])
            page.get_by_role("button", name="Earlier dates").click()
            expect_day(DATES[1])  # Range arrows also visit dates without events.
            page.locator("#calendar-next-matching-day").click()
            expect_day(DATES[2])
            page.locator("#calendar-search").fill("Alpha")
            page.locator("#calendar-next-matching-day").click()
            expect_day(DATES[4])  # Matching navigation honors the filter.
            page.evaluate("location.hash = 'calendar-day-2026-11-23'")
            expect_day(DATES[0])
            page.reload()
            expect_day(DATES[0])  # Return links and reloads respect selected date.
            page.locator('[data-calendar-mode="month"]').click()
            from playwright.sync_api import expect
            expect(page.locator(".calendar-day:visible")).to_have_count(len(DATES))
            page.locator('[data-calendar-mode="day"]').click()
            expect_day(DATES[0])
        finally:
            browser.close()
