"""Release 678: render real Workout Activity fragment and inspect computed CSS."""
from pathlib import Path
import os
import pytest
from playwright.sync_api import sync_playwright
from app.templating import templates

ROOT = Path(__file__).resolve().parents[1]
WORKOUT_CSS = (ROOT / "app/static/css/tracker-workout-dashboard661.css").read_text()
DAILY_CSS = (ROOT / "app/static/css/tracker-daily-flow559.css").read_text()


@pytest.mark.parametrize("width", (320, 375, 390, 430, 768, 1280))
@pytest.mark.parametrize("active", (False, True))
def test_678_workout_activity_links_are_styled_cards(width, active):
    summary = {
        "sessions7": 0, "days7": 0, "sessions28": 0,
        "days28": 0, "sets28": 0, "reps28": 0,
        "recent": [], "in_progress": active,
    }
    fragment = templates.env.get_template("_workout_dashboard661.html").render(
        workout_summary=summary
    )
    html = (
        '<!doctype html><html><head>'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<style>'
        ':root{--surface:#fff;--border:#d4dbe4;--ink:#192c31;'
        '--teal:#1265ad;--teal-ink:#fff;--wash:#f1f5f9}'
        '*{box-sizing:border-box}body{margin:0;font:16px system-ui}'
        '#main-content{padding:8px}'
        '#main-content a{color:#1265ad;text-decoration:underline}'
        '.dashboard-panel{padding:12px;border:1px solid #aaa;border-radius:12px}'
        '</style><style>' + DAILY_CSS + '</style><style>' +
        WORKOUT_CSS + '</style></head><body><main id="main-content">' +
        '<nav class="tracker-daily-flow559-links">'
        '<a href="#reference"><strong>Daily Shortcut</strong></a></nav>' +
        fragment + '</main></body></html>'
    )
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None,
        )
        try:
            page = browser.new_page(viewport={"width": width, "height": 820})
            page.set_content(html)
            cards = page.locator(
                "#tracker-workout-dashboard661 nav.tracker-workout-shortcuts678 > a"
            )
            assert cards.count() == 6
            assert [x for x in cards.evaluate_all(
                "els => els.map(el => el.getAttribute('href'))"
            )] == [
                "/workouts/quick", "/workouts/analytics", "/workouts/insights",
                "/workouts/routines", "/workouts/calendar", "/workouts",
            ]
            styles = cards.evaluate_all("""els => els.map(el => {
              const css=getComputedStyle(el), box=el.getBoundingClientRect();
              const label=getComputedStyle(el.querySelector('strong'));
              return {decoration:css.textDecorationLine, labelDecoration:label.textDecorationLine,
                      display:css.display, weight:label.fontWeight, radius:css.borderRadius,
                      background:css.backgroundColor, height:box.height, width:box.width};
            })""")
            reference_radius = page.locator(
                ".tracker-daily-flow559-links a"
            ).evaluate("el => getComputedStyle(el).borderRadius")
            assert all(card["decoration"] == "none" for card in styles), styles
            assert all(card["labelDecoration"] == "none" for card in styles), styles
            assert all(card["display"] == "flex" for card in styles), styles
            assert all(card["radius"] == reference_radius for card in styles)
            assert all(card["height"] >= 44 and card["width"] > 0 for card in styles)
            assert styles[0]["background"] != styles[1]["background"]
            assert cards.first.inner_text() == (
                "Resume Gym Mode" if active else "Open Rapid Gym Mode"
            )
            backfill = page.locator(".tracker-workout-empty-action678")
            assert backfill.count() == 1
            assert backfill.evaluate(
                "el => getComputedStyle(el).textDecorationLine"
            ) == "none"
            assert backfill.evaluate(
                "el => el.getBoundingClientRect().height"
            ) >= 44
            assert page.evaluate(
                "() => document.documentElement.scrollWidth <= innerWidth + 1"
            )
        finally:
            browser.close()
