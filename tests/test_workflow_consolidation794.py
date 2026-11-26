"""Release 794: shared forecast, date range and navigation contracts."""
from datetime import date, timedelta
from pathlib import Path
import os
import re

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.main import app
from app.models import LabReport, LabResult, RegimenSchedule
from app.routers import planning_hub
from tests.test_labs_overview import lab_overview_client
from tests.test_release778_regimen_return import env, item
from tests.test_calendar_action_buttons787 import rendered

ROOT = Path(__file__).resolve().parents[1]


def test_794_planning_default_filters_the_canonical_fefo_rows(monkeypatch):
    today = date.today()
    source = [
        {"compound": "Synthetic A", "unit": "mg", "dated_stock": 10,
         "unknown_stock": 0, "incomplete": True, "expired_existing": 0,
         "horizons": {28: {"shortage": 2, "expired": 0, "demand": 12,
                           "consumed": 10, "remaining": 0, "first_shortage": today}}},
        {"compound": "Synthetic B", "unit": "IU", "dated_stock": 20,
         "unknown_stock": 0, "incomplete": False, "expired_existing": 0,
         "horizons": {28: {"shortage": 0, "expired": 0, "demand": 10,
                           "consumed": 10, "remaining": 10, "first_shortage": None}}},
    ]
    monkeypatch.setattr(planning_hub, "build_fefo", lambda db: (source, ["Synthetic schedule warning"]))
    def must_not_run(db):
        raise AssertionError("Detailed comparison must be loaded only on demand")
    monkeypatch.setattr(planning_hub, "build_planning", must_not_run)
    with TestClient(app) as client:
        result = client.get("/planning-hub?horizon=28&category=shortage")
        assert result.status_code == 200
        assert "Synthetic A" in result.text and "Synthetic B" not in result.text
        assert "Provisional" in result.text
        assert "Synthetic schedule warning" in result.text
        assert 'href="/planning-hub?view=details"' in result.text
        assert 'href="/planning-priorities.csv?horizon=28&amp;compound=&amp;category=shortage"' in result.text
        result = client.get("/planning-hub?horizon=28&compound=Synthetic+B")
        assert result.status_code == 200
        assert "Synthetic B" in result.text and "Synthetic A" not in result.text


def test_794_legacy_planning_views_are_still_reachable():
    with TestClient(app) as client:
        for route in ("/planning-hub?view=details", "/planning-priorities",
                      "/planning-hub.csv", "/planning-priorities.csv",
                      "/inventory-forecast", "/scheduled-forecast", "/fefo-forecast"):
            assert client.get(route).status_code == 200, route


def test_794_labs_date_range_filters_reports_and_trends(lab_overview_client):
    client, engine = lab_overview_client
    today = date.today()
    with Session(engine) as db:
        for age, label, analyte in [(0,"Current synthetic", "CurrentAnalyte"),
                                    (29,"Boundary synthetic", "BoundaryAnalyte"),
                                    (30,"Old synthetic", "OldAnalyte")]:
            db.add(LabReport(drawn_on=today-timedelta(days=age), lab_name=label,
                             results=[LabResult(analyte=analyte,value=1,unit="mg/dL")]))
        db.commit()
    result = client.get("/labs?days=30")
    assert result.status_code == 200
    assert "Current synthetic" in result.text and "Boundary synthetic" in result.text
    assert "CurrentAnalyte" in result.text and "BoundaryAnalyte" in result.text
    assert "Old synthetic" not in result.text and "OldAnalyte" not in result.text
    assert 'href="/progress?days=30"' in result.text
    assert 'value="30" selected' in result.text
    assert "OldAnalyte" in client.get("/labs").text
    assert "OldAnalyte" in client.get("/labs?days=90").text


def test_794_catalog_item_schedule_handoff_is_read_only(env):
    client, factory = env
    assert item(client).status_code == 303
    result = client.get("/regimen?schedule_item=1")
    assert result.status_code == 200
    assert '<details id="reg635-add-schedule" open>' in result.text
    section = result.text.split('id="reg635-add-schedule"', 1)[1]
    options = section.split('name="item_id"',1)[1].split("</select>",1)[0]
    assert re.search(r'<option value="1"[^>]*selected', options)
    with factory() as db:
        assert list(db.scalars(select(RegimenSchedule))) == []


@pytest.mark.parametrize("width",[390,1440])
def test_794_home_tabs_fit_available_width(width):
    with TestClient(app) as client:
        pages = [(url, *rendered(client,url)) for url in ("/","/mobile")]
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True,executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None)
        try:
            page = browser.new_page(viewport={"width":width,"height":900})
            page.route("**/*",lambda route:route.abort())
            for url, markup, css in pages:
                page.set_content(markup)
                page.add_style_tag(content=css)
                nav = page.locator('nav[aria-label="Home workspace"]')
                assert nav.locator('a[aria-current="page"]').get_attribute("href") == url
                assert nav.locator("a").count() == 2
                assert nav.evaluate("""el => {
                    const a=[...el.querySelectorAll('a')].map(x=>x.getBoundingClientRect());
                    return Math.abs(a[0].y-a[1].y)<2 && a[0].width>0 && a[1].right<=el.getBoundingClientRect().right+1;
                }""")
        finally:
            browser.close()


def test_794_gym_guard_covers_directory_routine_links_and_native_picker():
    markup = """<main id="workout659-root">
    <form id="workout659-log-form"><input name="reps" value="8"></form>
    <div class="workout766-handoff"><a id="next" href="/workouts/quick?machine=2">Next</a></div>
    <div class="workout662-directory"><a id="directory" href="/workouts/quick?machine=3">Directory</a></div>
    <div><a id="routine" href="/workouts/quick?machine=4">Routine</a></div>
    <form class="workout659-machine-picker" action="/workouts/quick"><select name="machine">
    <option value="1" selected>One</option><option value="2">Two</option></select><button>Go</button></form>
    </main>"""
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=os.environ.get("TRACKER_TEST_CHROMIUM_PATH") or None)
        try:
            page=browser.new_page()
            page.route("**/*",lambda route:route.fulfill(status=200,content_type="text/html",body=markup))
            page.goto("http://tracker.test/workouts/quick?machine=1")
            page.add_script_tag(content=(ROOT/"app/static/js/tracker-gym-handoff766.js").read_text())
            page.evaluate("window.confirmCount=0;window.confirm=()=>{window.confirmCount++;return false}")
            page.locator('input[name="reps"]').fill("9")
            for ident in ("next","directory","routine"):
                assert page.locator("#"+ident).evaluate("el => !el.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}))")
            assert page.evaluate("window.confirmCount") == 3
            assert page.locator("form.workout659-machine-picker").evaluate("""form=>{
                form.querySelector('select').value='2';
                return !form.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));
            }""")
            assert page.locator('select[name="machine"]').input_value() == "1"
            assert page.evaluate("window.confirmCount") == 4
        finally:
            browser.close()
