"""Release 738: integrated MACD behavior, mobile actions and no-cascade CSS merges.

Disposable per-test SQLite with FK ON; no production data.
"""
import json
from pathlib import Path
from urllib.parse import urlencode

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jinja2 import Environment
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.models import (
    ChangeAudit, RegimenItem, RegimenSchedule, RegimenEntry,
    RegimenTabletSchedule731, RegimenTabletEntry731,
)
from app.routers import regimen635

ROOT = Path(__file__).resolve().parents[1]
TPL = ROOT / "app/templates"
CSS = ROOT / "app/static/css"
FOOD_LEGACY = ("374", "375", "376", "377", "378", "379", "380",
               "381", "382", "384", "423", "424", "425")


@pytest.fixture
def env(tmp_path):
    engine = create_engine(
        "sqlite:///" + str(tmp_path / "regimen738.sqlite"),
        connect_args={"check_same_thread": False},
    )
    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    app = FastAPI()
    app.include_router(regimen635.router)

    def scoped():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = scoped
    with TestClient(app, follow_redirects=False) as client:
        yield client, Session
    engine.dispose()


def post(client, url, data=None):
    response = client.post(
        url, content=urlencode(data or {}),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 303, response.text
    return response


def create_item(client, kind, name):
    response = post(client, "/regimen/items", {
        "kind": kind, "name": name, "strength": "20 mg", "form": "Tablet",
    })
    assert "err=" not in response.headers["location"]


def create_schedule(client, item_id, *, tablet=False):
    values = {"item_id": str(item_id), "cadence": "daily",
              "start_on": "2026-11-21", "amount": "1 tablet"}
    if tablet:
        values.update(tablet_mode="tablet", tablet_strength_mg="20",
                      prescribed_dose_mg="10", tablets_planned="0.5")
    response = post(client, "/regimen/schedules", values)
    assert "err=" not in response.headers["location"]


def create_entry(client, item_id, schedule_id):
    response = post(client, "/regimen/entries", {
        "item_id": str(item_id), "schedule_id": str(schedule_id),
        "outcome": "taken", "logged_at": "2026-11-21T08:30",
        "amount": "1 tablet",
    })
    assert "err=" not in response.headers["location"]


def test_738_supplement_delete_requires_confirmation_then_cleans_dependents(env):
    client, Session = env
    create_item(client, "supplement", "Vitamin example")
    create_schedule(client, 1)
    create_entry(client, 1, 1)
    create_item(client, "medication", "Keep medication")

    assert "err=" in post(client, "/regimen/items/1/delete-supplement").headers["location"]
    assert "err=" in post(client, "/regimen/items/1/delete", {
        "confirm_delete": "delete",
    }).headers["location"]
    with Session() as db:
        assert db.get(RegimenItem, 1) is not None
        assert db.get(RegimenTabletSchedule731, 1) is None

    deleted = post(client, "/regimen/items/1/delete-supplement", {
        "confirm_delete": "delete",
    })
    assert "err=" not in deleted.headers["location"]
    with Session() as db:
        assert db.get(RegimenItem, 1) is None
        assert db.get(RegimenSchedule, 1) is None
        assert db.get(RegimenEntry, 1) is None
        assert db.get(RegimenTabletSchedule731, 1) is None
        assert db.get(RegimenItem, 2).kind == "medication"
        audits = list(db.scalars(select(ChangeAudit).where(ChangeAudit.action == "delete")))
        assert {"regimen_item", "regimen_schedule", "regimen_entry"} <= {a.entity_type for a in audits}
        before = json.loads(next(a.before_json for a in audits
                                 if a.entity_type == "regimen_item"))
        assert (before["kind"], before["schedules_deleted"],
                before["intakes_deleted"]) == ("supplement", 1, 1)
    assert client.post("/regimen/items/1/delete-supplement",
                       data={"confirm_delete": "delete"}).status_code == 404


def test_738_supplement_delete_cannot_delete_medication_or_crosslinked_history(env):
    client, Session = env
    create_item(client, "medication", "Keep medication")
    create_item(client, "supplement", "Supplement")
    create_schedule(client, 2)
    assert "err=" in post(client, "/regimen/items/1/delete-supplement",
                          {"confirm_delete": "delete"}).headers["location"]
    # A corrupt intake linking a different item to this schedule must fail closed.
    from datetime import datetime
    with Session() as db:
        db.add(RegimenEntry(
            item_id=1, schedule_id=1, logged_at=datetime(2026, 11, 21, 8),
            outcome="taken", amount="1 tablet", meal="", notes="",
        ))
        db.commit()
    assert "err=" in post(client, "/regimen/items/2/delete-supplement",
                          {"confirm_delete": "delete"}).headers["location"]
    with Session() as db:
        assert db.get(RegimenItem, 1) is not None
        assert db.get(RegimenItem, 2) is not None
        assert db.get(RegimenSchedule, 1) is not None


def test_738_delete_empty_schedule_and_tablet_plan_preserves_item_and_audit(env):
    client, Session = env
    create_item(client, "medication", "Prescription")
    create_schedule(client, 1, tablet=True)
    assert "err=" in post(client, "/regimen/schedules/1/delete").headers["location"]
    with Session() as db:
        assert db.get(RegimenSchedule, 1) is not None
        assert db.get(RegimenTabletSchedule731, 1) is not None
    result = post(client, "/regimen/schedules/1/delete", {"confirm_delete": "delete"})
    assert "err=" not in result.headers["location"]
    with Session() as db:
        assert db.get(RegimenSchedule, 1) is None
        assert db.get(RegimenTabletSchedule731, 1) is None
        assert db.get(RegimenItem, 1) is not None
        actions = list(db.scalars(select(ChangeAudit).where(
            ChangeAudit.entity_type == "regimen_schedule",
            ChangeAudit.action == "delete",
        )))
        assert len(actions) == 1


def test_738_schedule_with_intake_cannot_be_deleted_but_can_be_stopped(env):
    client, Session = env
    create_item(client, "supplement", "Daily supplement")
    create_schedule(client, 1)
    create_entry(client, 1, 1)
    blocked = post(client, "/regimen/schedules/1/delete", {"confirm_delete": "delete"})
    assert "err=" in blocked.headers["location"]
    stopped = post(client, "/regimen/schedules/1/stop")
    assert "err=" not in stopped.headers["location"]
    with Session() as db:
        assert db.get(RegimenSchedule, 1).active is False
        assert db.get(RegimenEntry, 1).schedule_id == 1


def test_738_live_regimen_has_visible_semantic_macd_and_history_protection(env):
    client, Session = env
    src = (TPL / "regimen635.html").read_text()
    Environment().parse(src)
    create_item(client, "medication", "Medicine")
    create_item(client, "supplement", "Supplement")
    create_schedule(client, 1)
    create_schedule(client, 2)
    create_entry(client, 2, 2)
    response = client.get("/regimen?day=2026-11-21")
    assert response.status_code == 200
    page = response.text
    assert 'action="/regimen/items/1/delete"' in page
    assert 'action="/regimen/items/2/delete-supplement"' in page
    assert 'action="/regimen/schedules/1/delete"' in page
    assert 'action="/regimen/schedules/2/delete"' not in page
    assert "Intake history retained" in page
    assert 'action="/regimen/entries/1/delete"' in page
    assert 'data-reg738-intake-actions' in page
    for label in ("Edit medication", "Edit supplement", "Edit schedule",
                  "Edit intake", "Delete intake", "Delete supplement",
                  "Delete medication", "Delete schedule"):
        assert label in page
    assert "data-label=\"Date/time\"" in page
    assert "data-label=\"Actions\"" in page


def test_738_food_style_merge_preserves_rule_bytes_and_single_link():
    src = (TPL / "food.html").read_text()
    Environment().parse(src)
    combined = (CSS / "tracker-food-core738.css").read_text()
    original = "".join(
        (CSS / f"tracker-food{n}.css").read_text().rstrip() + "\n"
        for n in FOOD_LEGACY
    )
    assert combined == original
    assert src.count("tracker-food-core738.css?v=738") == 1
    for n in FOOD_LEGACY:
        assert f'tracker-food{n}.css?v={n}' not in src
    assert src.index("tracker-food-core738.css?v=738") < src.index(
        "tracker-mobile-daily602.css?v=602"
    ) < src.index("tracker-food-ux673.css?v=673")


def test_738_workout_action_css_merge_retains_order_and_semantic_forms():
    original = (
        (CSS / "tracker-action-nav675.css").read_text().rstrip() + "\n"
        + (CSS / "tracker-integrated-flow696.css").read_text().rstrip() + "\n"
    )
    assert (CSS / "tracker-action-flow738.css").read_text() == original
    for path in ("workouts654.html", "workout_quick659.html"):
        src = (TPL / path).read_text()
        Environment().parse(src)
        assert src.count("tracker-action-flow738.css?v=738") == 1
        assert "tracker-action-nav675.css?v=675" not in src
        assert "tracker-integrated-flow696.css?v=696" not in src
        assert "Finish &amp; Review" in src
        assert 'formaction="/workouts/finish-review"' in src


@pytest.mark.parametrize("width", [320, 390, 760, 1024])
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_738_mobile_regimen_actions_remain_visible_and_history_stacks(env, width, scheme):
    from playwright.sync_api import expect, sync_playwright

    client, _ = env
    create_item(client, "supplement", "Supplement")
    create_schedule(client, 1)
    create_entry(client, 1, 1)
    html = client.get("/regimen?day=2026-11-21").text
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page(
                viewport={"width": width, "height": 844},
                color_scheme=scheme,
            )
            page.set_content(html)
            page.add_style_tag(content=(ROOT / "app/static/app.css").read_text())
            add = page.locator('form[action="/regimen/items/1/delete-supplement"] button')
            expect(add).to_be_visible()
            assert add.evaluate("el => el.getBoundingClientRect().height >= 44")
            edit = page.locator("[data-reg738-intake-actions] summary")
            delete = page.locator("[data-reg738-intake-actions] > form > button")
            expect(edit).to_have_text("Edit intake")
            expect(delete).to_have_text("Delete intake")
            assert edit.evaluate("el => el.getBoundingClientRect().height >= 44")
            assert delete.evaluate("el => el.getBoundingClientRect().height >= 44")
            detail = page.locator("[data-reg738-intake-actions] details")
            assert not detail.evaluate("el => el.open")
            edit.click()
            expect(detail).to_have_attribute("open", "")
            assert detail.locator('form[action="/regimen/entries/1/edit"]').is_visible()
            if width <= 760:
                assert page.locator("#reg635-history tbody tr").first.evaluate(
                    "el => getComputedStyle(el).display == 'block'"
                )
            assert page.evaluate(
                "document.documentElement.scrollWidth <= innerWidth"
            ), (width, scheme)
        finally:
            browser.close()


@pytest.mark.parametrize("width", [320, 390, 760, 1024])
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_738_original_and_merged_css_have_equal_browser_actions(width, scheme):
    from playwright.sync_api import sync_playwright
    original = (
        (CSS / "tracker-action-nav675.css").read_text().rstrip() + "\n"
        + (CSS / "tracker-integrated-flow696.css").read_text().rstrip() + "\n"
    )
    merged = (CSS / "tracker-action-flow738.css").read_text()
    fixture = (
        '<!doctype html><html><head><meta name="viewport" '
        'content="width=device-width,initial-scale=1">'
        '<style id="subject"></style></head><body>'
        '<nav class="ux675-actions"><a href="#">Workouts</a>'
        '<details class="ux675-more"><summary>More</summary><div>Tools</div></details></nav>'
        '<nav class="tracker-flow696-actions"><a href="#">New</a>'
        '<details class="tracker-flow696-more"><summary>More actions</summary>'
        '<div>More</div></details></nav></body></html>'
    )
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page(
                viewport={"width": width, "height": 844},
                color_scheme=scheme,
            )
            page.set_content(fixture)
            def render(css):
                page.locator("#subject").evaluate(
                    "(el, data) => el.textContent = data", css
                )
                return page.locator("nav").evaluate_all(
                    """els => els.map(el => {
                        const s = getComputedStyle(el);
                        return [s.display, s.gap, s.margin, s.width];
                    })"""
                )
            assert render(original) == render(merged), (width, scheme)
        finally:
            browser.close()
