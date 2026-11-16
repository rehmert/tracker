"""Release 659: real Chromium phone-sized exercise controls and rest-timer persistence.

Uses shipped JavaScript with an isolated mock document and no live app/DB.
Server validation is exercised separately by tests/test_workouts659.py.
"""
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

pytestmark = pytest.mark.browser
SCRIPT = (Path(__file__).resolve().parents[2] /
          "app/static/js/tracker-workouts659.js").read_text()
URL = "http://tracker.test/workouts/quick"


def html(*, logged: bool, last_id: int):
    return f"""<!doctype html><html><head>
      <meta name="viewport" content="width=device-width, initial-scale=1">
    </head><body>
      <section id="workout659-root" data-session-id="101"
        data-last-set-id="{last_id}" data-logged="{'yes' if logged else 'no'}">
        <form id="workout659-log-form">
          <button id="workout659-minusweight" type="button" data-step659="weight"
            data-delta659="-5">-5</button>
          <input name="weight_lb" value="95.5" type="number" step="any">
          <button id="workout659-plusweight" type="button" data-step659="weight"
            data-delta659="5">+5</button>
          <button type="button" data-step659="reps" data-delta659="-1">-1</button>
          <input name="reps" type="number" value="12">
          <button type="button" data-step659="reps" data-delta659="1">+1</button>
          <button id="workout659-save" type="submit">Save Set</button>
        </form>
        <form class="workout659-repeat">
          <button type="submit">Repeat</button>
        </form>
        <select id="workout659-rest-duration">
          <option value="60">60 sec</option>
          <option value="90" selected>90 sec</option>
          <option value="120">120 sec</option>
          <option value="180">180 sec</option>
        </select>
        <output id="workout659-rest-display" role="timer">01:30</output>
        <p id="workout659-rest-status" role="status"></p>
        <button type="button" id="workout659-rest-start">Start</button>
        <button type="button" id="workout659-rest-reset">Reset</button>
      </section>
      <script>{SCRIPT}</script></body></html>"""


@pytest.mark.parametrize("width,height", [(393, 852), (390, 844)])
def test_659_rapid_touch_steppers_and_timer_survive_machine_navigation(width, height):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": width, "height": height}, is_mobile=True,
            has_touch=True, device_scale_factor=3,
        )
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.route(
            "**/workouts/quick*",
            lambda route: route.fulfill(
                status=200, content_type="text/html",
                body=html(
                    logged="logged=1" in route.request.url,
                    last_id=101 if "machine=1" in route.request.url else 102,
                ),
            ),
        )
        try:
            page.goto(URL + "?machine=1&logged=1")
            expect(page.locator("#workout659-rest-display")).to_have_text("01:30")
            page.locator("#workout659-plusweight").click()
            expect(page.locator('input[name="weight_lb"]')).to_have_value("100.5")
            page.get_by_role("button", name="+1").click()
            expect(page.locator('input[name="reps"]')).to_have_value("13")
            page.get_by_role("button", name="-1").click()
            expect(page.locator('input[name="reps"]')).to_have_value("12")

            stored_before = page.evaluate(
                "sessionStorage.getItem('tracker-workout659:101:deadline')"
            )
            assert stored_before and int(stored_before) > 0
            # Navigating to a new machine must retain the same expiry.
            page.goto(URL + "?machine=2")
            stored_after = page.evaluate(
                "sessionStorage.getItem('tracker-workout659:101:deadline')"
            )
            assert stored_after == stored_before
            assert "Resting" in page.locator("#workout659-rest-status").inner_text()

            # Reload of the previously logged page cannot restart the timer.
            page.goto(URL + "?machine=1&logged=1")
            stored_reloaded = page.evaluate(
                "sessionStorage.getItem('tracker-workout659:101:deadline')"
            )
            assert stored_reloaded == stored_before
            page.locator("#workout659-rest-reset").click()
            expect(page.locator("#workout659-rest-display")).to_have_text("01:30")
            assert page.evaluate(
                "sessionStorage.getItem('tracker-workout659:101:deadline')"
            ) is None

            page.locator("#workout659-rest-duration").select_option("120")
            page.locator("#workout659-rest-start").click()
            expect(page.locator("#workout659-rest-display")).to_have_text("02:00")
            assert not errors, errors
        finally:
            context.close()
            browser.close()
