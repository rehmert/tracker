"""Release 745: real water MACD corrections and gym CSS parity."""
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool
from jinja2 import Environment
from app.food_water425 import init_water_schema, water_report
from app.routers import food, food_quick375

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "app/static/css"
TPL = ROOT / "app/templates"
PARTS = ("tracker-workouts659.css", "tracker-workout-targets666.css",
         "tracker-workout-gym667.css", "tracker-action-flow738.css",
         "tracker-workouts716.css")


@pytest.fixture
def journal(monkeypatch):
    engine = create_engine("sqlite://",
        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    monkeypatch.setattr(food, "engine", engine)
    monkeypatch.setattr(food_quick375, "engine", engine)
    init_water_schema(engine)
    app = FastAPI()
    app.include_router(food.router)
    with TestClient(app) as client:
        yield client, engine
    engine.dispose()


def test_745_move_water_to_other_day_and_correct_amount(journal):
    client, engine = journal
    r = client.post("/food/water",
        data={"day":"2026-11-05", "ounces":"20"}, follow_redirects=False)
    assert r.status_code == 303
    row = water_report("2026-11-05",engine)["entries"][0]
    r = client.post("/food/water/%d/edit" % row["id"],
        data={"original_day":"2026-11-05", "day":"2026-11-06",
              "ounces":"32.125"}, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/food?day=2026-11-06#food-water"
    assert water_report("2026-11-05",engine)["count"] == 0
    newer = water_report("2026-11-06",engine)["entries"]
    assert len(newer) == 1 and newer[0]["id"] == row["id"]
    assert newer[0]["ounces"] == 32.13
    with engine.connect() as db:
        assert db.execute(text("SELECT COUNT(*) FROM tracker_water_entries")).scalar_one() == 1


@pytest.mark.parametrize("patch,code",[
    ({"original_day":"2026-11-07"},404),
    ({"day":"not-a-date"},422),
    ({"ounces":"0"},422),
    ({"ounces":"nan"},422),
    ({"ounces":"9999"},422),
    ({"ounces":"0.001"},422)])
def test_745_invalid_water_edits_do_not_change_history(journal,patch,code):
    client,engine = journal
    client.post("/food/water",data={"day":"2026-11-05","ounces":"16"})
    row=water_report("2026-11-05",engine)["entries"][0]
    values={"original_day":"2026-11-05","day":"2026-11-06","ounces":"24"}
    values.update(patch)
    resp=client.post("/food/water/%d/edit"%row["id"],
        data=values, follow_redirects=False)
    assert resp.status_code == code
    assert water_report("2026-11-05",engine)["entries"][0]["ounces"] == 16
    assert water_report("2026-11-06",engine)["count"] == 0


def test_745_water_edit_is_native_visible_and_touch_friendly():
    html=(TPL/"food.html").read_text()
    Environment().parse(html)
    assert 'action="/food/water/{{ entry.id }}/edit"' in html
    assert 'name="original_day" value="{{ day }}"' in html
    assert "Save correction" in html
    assert "Delete this water entry?" in html
    assert 'tracker-food-ux673.css?v=745' in html
    css=(CSS/"tracker-food-ux673.css").read_text()
    assert ".food745-water-edit" in css
    assert "min-height:44px" in css


def test_745_gym_css_bundle_exact_concatenation_and_single_link():
    old="".join((CSS/p).read_text().rstrip()+"\n" for p in PARTS)
    assert (CSS/"tracker-workout-gym-bundle745.css").read_text() == old
    html=(TPL/"workout_quick659.html").read_text()
    Environment().parse(html)
    assert html.count("tracker-workout-gym-bundle745.css?v=745") == 1
    for p in PARTS:
        assert p not in html
    assert 'action="/workouts/quick/start"' in html


@pytest.mark.parametrize("width",(320,390,430,760,1024))
@pytest.mark.parametrize("scheme",("light","dark"))
def test_745_gym_computed_parity_no_overflow(width,scheme):
    from playwright.sync_api import sync_playwright
    old="".join((CSS/p).read_text().rstrip()+"\n" for p in PARTS)
    merged=(CSS/"tracker-workout-gym-bundle745.css").read_text()
    html=('<meta name="viewport" content="width=device-width,initial-scale=1">'
          '<style id="gym-rules"></style><section class="workout659">'
          '<div class="workout659-panel"><h2>Log Set</h2>'
          '<button class="workout659-main-button">Save Set</button>'
          '<div class="workout667-active-goal">Goal</div>'
          '<div class="workout662-nav"><a href="#next">Next Machine</a></div>'
          '</div></section>')
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        try:
            page=browser.new_page(viewport={"width":width,"height":844},
                                  color_scheme=scheme)
            page.set_content(html)
            def measure(rules):
                page.locator("#gym-rules").evaluate(
                    "(element, value) => element.textContent = value",rules)
                return page.evaluate("""() => ({
                  styles:['.workout659-panel','.workout659-main-button',
                          '.workout667-active-goal','.workout662-nav a']
                   .map(sel => {const s = getComputedStyle(document.querySelector(sel));
                     return [s.display,s.padding,s.minHeight,s.borderRadius,s.fontSize,s.gap];}),
                  fits:document.documentElement.scrollWidth <= innerWidth + 1
                })""")
            expected=measure(old)
            assert expected == measure(merged)
            assert expected["fits"]
        finally:
            browser.close()
