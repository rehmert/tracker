"""Release 665: Chromium mobile browser-local targets plus shipped planner template."""
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from playwright.sync_api import expect, sync_playwright

from app.templating import templates

ROOT = Path(__file__).resolve().parents[2]
PAGE = (ROOT / "app/templates/workout_plan665.html").read_text()
BODY = PAGE.split("{% block content %}", 1)[1].rsplit("{% endblock %}", 1)[0]
CSS = (ROOT / "app/static/css/tracker-workout-plan665.css").read_text()
JS = (ROOT / "app/static/js/tracker-workout-plan665.js").read_text()
URL = "https://tracker.test/workouts/routines/99/plan"


def markup665(routine_id=99):
    latest = SimpleNamespace(
        session_id=51, started_at=datetime(2026, 5, 18, 9),
        sets=2, reps=18, heaviest_lb=100., volume=1700.,
    )
    previous = SimpleNamespace(
        session_id=42, started_at=datetime(2026, 5, 6, 9),
        sets=2, reps=22, heaviest_lb=80., volume=1700.,
    )
    rows = [
        {
            "item": SimpleNamespace(id=701),
            "equipment": SimpleNamespace(id=50, name="Seated Press", gym="East Gym"),
            "latest": latest, "previous": previous,
            "load_change": 20., "volume_change": 0.,
        },
        {
            "item": SimpleNamespace(id=702),
            "equipment": SimpleNamespace(id=51, name="Cable Row", gym="West Gym"),
            "latest": None, "previous": None,
            "load_change": None, "volume_change": None,
        },
    ]
    html = templates.env.from_string(BODY).render(
        routine=SimpleNamespace(id=routine_id, name="Upper A"),
        rows=rows, history_count=1,
    )
    return (
        '<!doctype html><html><head>'
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<style>*{box-sizing:border-box}body{margin:0;padding:12px}'
        + CSS + '</style></head><body>'
        + html + '<script>' + JS + '</script></body></html>'
    )


@pytest.mark.browser
@pytest.mark.parametrize("width,height", [(320, 740), (390, 844), (393, 852)])
def test_665_phone_user_entered_targets_are_private_and_persist_per_routine(width, height):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": width, "height": height},
            is_mobile=True, has_touch=True, device_scale_factor=3,
        )
        page = context.new_page()
        errors = []
        requests = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("request", lambda request: requests.append(
            (request.method, request.url)
        ))
        page.route("**/workouts/routines/*/plan", lambda route: route.fulfill(
            status=200, content_type="text/html; charset=utf-8",
            body=markup665(
                routine_id=100 if "/100/" in route.request.url else 99
            ),
        ))
        try:
            page.goto(URL)
            assert page.evaluate("document.characterSet") == "UTF-8"
            expect(page.get_by_role("heading", name="Workout Program Planner")).to_be_visible()
            expect(page.locator(".workout665-exercise")).to_have_count(2)
            assert page.evaluate(
                "document.documentElement.scrollWidth <= window.innerWidth"
            ), f"Planner overflows {width}px"
            first = page.locator('.workout665-exercise[data-item-id665="701"]')
            assert "Change in heaviest load" in first.inner_text()
            assert "+20.0 lb" in first.inner_text()
            assert "0.0 lb × reps" in first.inner_text()
            assert "No completed sessions" in page.locator(
                '.workout665-exercise[data-item-id665="702"]'
            ).inner_text()

            first.locator('[data-field665="sets"]').fill("3")
            first.locator('[data-field665="sets"]').press("Tab")
            first.locator('[data-field665="reps"]').fill("10")
            first.locator('[data-field665="reps"]').press("Tab")
            first.locator('[data-field665="weight"]').fill("102.5")
            first.locator('[data-field665="weight"]').press("Tab")
            expect(page.locator("#workout665-save-status")).to_contain_text(
                "Targets saved only on this browser"
            )
            stored = page.evaluate(
                "JSON.parse(localStorage.getItem("
                "'tracker.workout665.plan.routine.99')).targets['701']"
            )
            assert stored == {
                "sets": "3", "reps": "10", "weight": "102.5",
            }

            # Disallow invalid targets without changing the last valid save.
            first.locator('[data-field665="sets"]').fill("21")
            first.locator('[data-field665="sets"]').press("Tab")
            expect(page.locator("#workout665-save-status")).to_contain_text(
                "Invalid target"
            )
            assert page.evaluate(
                "JSON.parse(localStorage.getItem("
                "'tracker.workout665.plan.routine.99')).targets['701'].sets"
            ) == "3"

            page.reload()
            first = page.locator('.workout665-exercise[data-item-id665="701"]')
            expect(first.locator('[data-field665="sets"]')).to_have_value("3")
            expect(first.locator('[data-field665="reps"]')).to_have_value("10")
            expect(first.locator('[data-field665="weight"]')).to_have_value("102.5")

            # A separate routine ID must not display the first routine's draft.
            page.goto("https://tracker.test/workouts/routines/100/plan")
            expect(page.locator(
                '.workout665-exercise[data-item-id665="701"] [data-field665="sets"]'
            )).to_have_value("")
            assert page.evaluate(
                "localStorage.getItem('tracker.workout665.plan.routine.100')"
            ) is None

            page.goto(URL)
            page.get_by_role("button", name="Clear Saved Targets").click()
            expect(first.locator('[data-field665="sets"]')).to_have_value("")
            expect(first.locator('[data-field665="reps"]')).to_have_value("")
            expect(first.locator('[data-field665="weight"]')).to_have_value("")
            assert page.evaluate(
                "localStorage.getItem('tracker.workout665.plan.routine.99')"
            ) is None
            assert all(method == "GET" for method, url in requests), requests
            assert not errors, errors
        finally:
            context.close()
            browser.close()
