"""Release 661: real phone-viewport dashboard panel and customization smoke.

Uses the shipped Jinja fragment, CSS and existing dashboard personalization JS;
all browser requests are mocked. No production server or database writes.
"""
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from playwright.sync_api import expect, sync_playwright

from app.templating import templates

ROOT = Path(__file__).resolve().parents[2]
CSS = (ROOT / "app/static/css/tracker-workout-dashboard661.css").read_text()
PREFERENCES_JS = (ROOT / "app/static/personalize.js").read_text()
URL = "https://tracker.test/dashboard-661"


def mock_document661():
    summary = {
        "sessions7": 3, "days7": 2,
        "sessions28": 8, "days28": 6,
        "recent": [
            SimpleNamespace(
                session_id=75,
                started_at=datetime(2026, 11, 16, 9),
                sets=4, machines=2,
            ),
        ],
        "in_progress": True,
        "limit": 5,
    }
    fragment = templates.get_template("_workout_dashboard661.html").render(
        workout_summary=summary
    )
    return (
        '<!doctype html><html><head>'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<style>*{box-sizing:border-box}body{margin:0;padding:12px}'
        '.dashboard-panel{padding:1rem;border:1px solid #999;border-radius:10px}'
        + CSS + '</style></head><body>'
        '<div class="dashboard-personalize">'
        '<button id="dashboard-customize" aria-expanded="false">Customize dashboard</button>'
        '<div id="dashboard-customize-panel" hidden>'
        '<div id="dashboard-customize-list"></div>'
        '<button id="dashboard-reset">Reset</button></div></div>'
        + fragment +
        '<section data-dashboard-panel="1" data-dashboard-title="At a glance">'
        '<h2>Other Dashboard Panel</h2></section></body></html>'
    )


@pytest.mark.parametrize("width,height", [(390, 844), (393, 852)])
def test_661_phone_card_and_dashboard_personalization(width, height):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": width, "height": height},
            is_mobile=True, has_touch=True, device_scale_factor=3,
        )
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.route("**/dashboard-661", lambda route: route.fulfill(
            status=200, content_type="text/html", body=mock_document661()
        ))
        try:
            page.goto(URL)
            card = page.locator("#tracker-workout-dashboard661")
            expect(card).to_be_visible()
            expect(card.get_by_role("heading", name="Workout Activity")).to_be_visible()
            expect(card.get_by_role("link", name="Resume Gym Mode")).to_have_attribute(
                "href", "/workouts/quick"
            )
            expect(card.get_by_role("link", name="Strength Progress")).to_have_attribute(
                "href", "/workouts/analytics"
            )
            expect(card.get_by_role("link", name="2026-11-16 09:00 EST")).to_have_attribute(
                "href", "/workouts/sessions/75"
            )
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), (
                f"Dashboard workout panel horizontally overflows {width}px"
            )

            # Established personalization must include the new panel in
            # existing show/hide/reorder, not introduce separate state.
            page.add_script_tag(content=PREFERENCES_JS)
            page.locator("#dashboard-customize").click()
            row = page.locator(".customize-row").filter(has_text="Workout activity")
            expect(row).to_have_count(1)
            checkbox = row.locator('input[type="checkbox"]')
            expect(checkbox).to_be_checked()
            checkbox.uncheck()
            expect(card).to_be_hidden()
            checkbox.check()
            expect(card).to_be_visible()
            assert not errors, errors
        finally:
            context.close()
            browser.close()
