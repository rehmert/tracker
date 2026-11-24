"""Exercise the shipped template and CSS in isolated Chromium, without live data."""
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
from jinja2 import Environment, FileSystemLoader, ChoiceLoader, DictLoader
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
T = ROOT / "app/templates"
STATIC = ROOT / "app/static"


def render(active=True):
    env = Environment(loader=ChoiceLoader([
        DictLoader({"base.html": '<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">{% block page_assets %}{% endblock %}</head><body>{% block content %}{% endblock %}</body></html>'}),
        FileSystemLoader(T),
    ]))
    env.filters["dt"] = str
    machine = NS(id=1, name="Chest Press", gym="Gym", seat_setting="4", setup_notes="Adjust seat")
    other = NS(id=2, name="Row", gym="Gym")
    return env.get_template("workout_quick659.html").render(
        active=NS(id=9) if active else None, equipment=[machine, other],
        machine=machine, last=NS(id=3, weight_lb=100, reps=12, effort=7),
        next_machine=other, request=NS(query_params={}), routine=None,
        routines=[], machine_sets=[], available_to_add716=[], equipment_kinds716=[],
        load_config668=None, progression674=None,
    )


@pytest.mark.parametrize("width", [320, 390, 430])
def test_782_rendered_mobile_gym(width):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": width, "height": 844}, is_mobile=True, has_touch=True)
        def route(r):
            path = r.request.url.split("?", 1)[0].split("/static/", 1)
            if len(path) == 2:
                file = STATIC / path[1]
                if file.is_file():
                    return r.fulfill(path=str(file), content_type="text/css" if file.suffix == ".css" else "application/javascript")
            return r.fulfill(status=200, content_type="text/html", body=render())
        page.route("**/*", route)
        page.goto("http://tracker.test/workouts/quick")
        expect(page.locator("#workout659-save")).to_be_visible()
        expect(page.locator("#workout659-weight")).to_have_value("100")
        expect(page.locator("#workout659-rest-display")).to_have_text("01:30")
        expect(page.locator("#workout662-search")).not_to_be_visible()
        expect(page.locator('input[name="effort"]')).not_to_be_visible()
        page.locator('[data-step659="weight"][data-delta659="5"]').click()
        expect(page.locator("#workout659-weight")).to_have_value("105")
        page.get_by_text("Fine adjustments & effort", exact=True).click()
        expect(page.locator('input[name="effort"]')).to_be_visible()
        page.locator('[data-step659="weight"][data-delta659="2.5"]').click()
        expect(page.locator("#workout659-weight")).to_have_value("107.5")
        page.get_by_text("Fine adjustments & effort", exact=True).click()
        page.locator("#workout662-directory > summary").click()
        expect(page.locator("#workout662-search")).to_be_visible()
        page.locator("#workout662-directory > summary").click()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.get_by_text("More machine tools", exact=True).click()
        page.get_by_text("Offline & Draft Tools", exact=True).click()
        expect(page.locator("#workout668-draft-save")).to_be_visible()
        browser.close()


def test_782_no_active_session_has_no_set_or_finish_action():
    html = render(False)
    assert "Start Free Workout" in html
    assert 'id="workout659-save"' not in html
    assert 'action="/workouts/quick/finish"' not in html
