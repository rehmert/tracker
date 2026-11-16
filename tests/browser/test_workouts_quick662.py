"""Release 662: phone Chromium on actual 659+662 JS, no backend/database writes."""
import re
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
SCRIPT659 = (ROOT / "app/static/js/tracker-workouts659.js").read_text()
SCRIPT662 = (ROOT / "app/static/js/tracker-workouts662.js").read_text()
CSS659 = (ROOT / "app/static/css/tracker-workouts659.css").read_text()
CSS662 = (ROOT / "app/static/css/tracker-workouts662.css").read_text()
URL = "https://tracker.test/workouts/quick"


def fixture662(machine=1, logged=False):
    selected1 = "selected" if machine == 1 else ""
    selected2 = "selected" if machine == 2 else ""
    current = "Press" if machine == 1 else "Row"
    last = 101 if machine == 1 else 102
    return f"""<!doctype html><html><head>
      <meta name="viewport" content="width=device-width,initial-scale=1">
      <style>*{{box-sizing:border-box}}body{{margin:0;padding:12px}}
        {CSS659}{CSS662}</style>
      </head><body>
      <section class="workout659" id="workout659-root"
          data-session-id="88" data-last-set-id="{last}"
          data-logged="{'yes' if logged else 'no'}">
        <form class="workout659-machine-picker" method="get" action="/workouts/quick">
          <label for="workout659-machine-select">Current machine</label>
          <div class="workout659-picker-row">
            <select id="workout659-machine-select" name="machine">
              <option value="1" {selected1}>Press · East Gym</option>
              <option value="2" {selected2}>Row · West Gym</option>
            </select>
            <button type="submit">Go</button>
          </div>
        </form>
        <details class="workout662-directory" id="workout662-directory">
          <summary>Find a machine by name (2 available)</summary>
          <label for="workout662-search">Search machine or gym</label>
          <input id="workout662-search" type="search">
          <p id="workout662-results" role="status"></p>
          <nav class="workout662-directory-list">
            <a href="/workouts/quick?machine=1" data-search662="Press East Gym">
              <strong>Press</strong><span>East Gym</span>
            </a>
            <a href="/workouts/quick?machine=2" data-search662="Row West Gym">
              <strong>Row</strong><span>West Gym</span>
            </a>
          </nav>
        </details>
        <h2>{current}</h2>
        <form id="workout659-log-form">
          <input name="weight_lb" type="number" step="any" value="95.5">
          <input name="reps" type="number" value="12">
          <button type="button" data-step659="weight" data-delta659="-2.5">-2.5 lb</button>
          <button type="button" data-step659="weight" data-delta659="2.5">+2.5 lb</button>
          <button type="button" data-step659="reps" data-delta659="-5">-5 reps</button>
          <button type="button" data-step659="reps" data-delta659="5">+5 reps</button>
          <button type="submit" id="workout659-save">Save Set</button>
          <button type="reset" class="workout662-restore">Restore last recorded values</button>
        </form>
        <nav class="workout662-nav">
          <a class="workout662-next" href="/workouts/quick?machine=2">Next Machine: Row →</a>
        </nav>
        <select id="workout659-rest-duration">
          <option value="60">60 sec</option>
          <option value="90" selected>90 sec</option>
          <option value="120">120 sec</option>
          <option value="180">180 sec</option>
        </select>
        <output id="workout659-rest-display" role="timer">01:30</output>
        <p id="workout659-rest-status" role="status"></p>
        <button type="button" id="workout659-rest-start">Start / Restart</button>
        <button type="button" id="workout659-rest-reset">Reset</button>
      </section>
      <script>{SCRIPT659}</script>
      <script>{SCRIPT662}</script>
      </body></html>"""


@pytest.mark.browser
@pytest.mark.parametrize("width,height", [(390, 844), (393, 852)])
def test_662_phone_search_adjust_reset_and_direct_machine_navigation(width, height):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": width, "height": height},
            is_mobile=True, has_touch=True, device_scale_factor=3,
        )
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))

        def respond(route):
            uri = route.request.url
            machine = 2 if "machine=2" in uri else 1
            route.fulfill(
                status=200, content_type="text/html",
                body=fixture662(machine=machine, logged="logged=1" in uri),
            )

        page.route("**/workouts/quick*", respond)
        try:
            page.goto(URL + "?machine=1&logged=1")
            timer = page.locator("#workout659-rest-display")
            expect(timer).to_have_text("01:30")
            deadline = page.evaluate(
                "sessionStorage.getItem('tracker-workout659:88:deadline')"
            )
            assert deadline and int(deadline) > 0

            weight = page.locator('input[name="weight_lb"]')
            reps = page.locator('input[name="reps"]')
            page.get_by_role("button", name="+2.5 lb").click()
            expect(weight).to_have_value("98")
            page.get_by_role("button", name="-2.5 lb").click()
            expect(weight).to_have_value("95.5")
            page.get_by_role("button", name="+5 reps").click()
            expect(reps).to_have_value("17")
            page.get_by_role("button", name="-5 reps").click()
            expect(reps).to_have_value("12")
            weight.fill("101.5")
            reps.fill("8")
            page.get_by_role("button", name="Restore last recorded values").click()
            expect(weight).to_have_value("95.5")
            expect(reps).to_have_value("12")

            page.get_by_text("Find a machine by name").click()
            search = page.get_by_label("Search machine or gym")
            search.fill("west")
            matches = page.locator(".workout662-directory-list a:visible")
            expect(matches).to_have_count(1)
            expect(matches.first).to_contain_text("Row")
            expect(page.locator("#workout662-results")).to_contain_text(
                "1 of 2 machines shown"
            )
            search.fill("no such machine")
            expect(matches).to_have_count(0)
            expect(page.locator("#workout662-results")).to_contain_text(
                "No matching machines"
            )
            search.fill("")
            expect(matches).to_have_count(2)

            page.get_by_label("Current machine").select_option("2")
            expect(page).to_have_url(re.compile(r"/workouts/quick\?machine=2$"))
            expect(page.get_by_role("heading", name="Row")).to_be_visible()
            assert page.evaluate(
                "sessionStorage.getItem('tracker-workout659:88:deadline')"
            ) == deadline
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            assert not errors, errors
        finally:
            context.close()
            browser.close()
