"""Release 733: visible MACD editing actions for medication, supplement and schedule.

No new write routes or schema: existing audited edits must remain functional.
"""
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jinja2 import Environment
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.models import RegimenItem, RegimenSchedule
from app.routers import regimen635

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "app/templates/regimen635.html"


@pytest.fixture
def env(tmp_path):
    engine = create_engine(
        "sqlite:///" + str(tmp_path / "macd733.sqlite"),
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def foreign_keys(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    app = FastAPI()
    app.include_router(regimen635.router)

    def database():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = database
    with TestClient(app, follow_redirects=False) as client:
        yield client, Session
    engine.dispose()


def post(client, path, values):
    response = client.post(
        path, content=urlencode(values),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 303, response.text
    assert "err=" not in response.headers["location"], response.headers["location"]
    return response


def seed(client):
    post(client, "/regimen/items", {
        "name": "Example medication", "kind": "medication",
        "strength": "20 mg", "form": "Tablet",
    })
    post(client, "/regimen/items", {
        "name": "Example supplement", "kind": "supplement",
        "strength": "500 mg", "form": "Capsule",
    })
    post(client, "/regimen/schedules", {
        "item_id": "1", "cadence": "daily", "start_on": "2026-11-21",
        "at_time": "08:30", "amount": "1 tablet", "meal": "",
    })


def test_733_regimen_jinja_and_edit_actions_are_both_visible_and_semantic(env):
    src = TEMPLATE.read_text(encoding="utf-8")
    Environment().parse(src)
    client, _ = env
    seed(client)
    page = client.get("/regimen?day=2026-11-21")
    assert page.status_code == 200
    content = page.text
    for label in ("Edit medication", "Edit supplement", "Edit schedule"):
        assert label in content
    for action in (
        'action="/regimen/items/1/edit"',
        'action="/regimen/items/2/edit"',
        'action="/regimen/schedules/1/edit"',
        'action="/regimen/items/1/delete"',
    ):
        assert action in content
    assert 'action="/regimen/items/2/delete"' not in content
    assert "data-reg733-item-actions" in content
    assert "data-reg733-schedule-actions" in content
    assert 'class="reg733-edit-trigger"' in content
    assert content.count('data-reg733-edit') >= 3
    assert "Add schedule" in content
    assert "Add supplement or medication" in content
    assert "Edit item</summary>" not in content


def test_733_existing_medication_supplement_and_schedule_edit_posts_work(env):
    client, Session = env
    seed(client)
    post(client, "/regimen/items/1/edit", {
        "kind": "medication", "name": "Corrected medication",
        "strength": "10 mg", "form": "Tablet",
        "ingredient": "Example active", "instructions": "As prescribed",
        "active": "yes",
    })
    post(client, "/regimen/items/2/edit", {
        "kind": "supplement", "name": "Corrected supplement",
        "strength": "250 mg", "form": "Capsule",
        "active": "yes",
    })
    post(client, "/regimen/schedules/1/edit", {
        "cadence": "daily", "start_on": "2026-11-23",
        "end_on": "", "at_time": "18:45",
        "amount": "0.5 tablet", "meal": "",
        "active": "yes",
    })
    with Session() as db:
        med, supplement = db.get(RegimenItem, 1), db.get(RegimenItem, 2)
        schedule = db.get(RegimenSchedule, 1)
        assert (med.name, med.strength, med.ingredient) == (
            "Corrected medication", "10 mg", "Example active",
        )
        assert (supplement.name, supplement.strength) == (
            "Corrected supplement", "250 mg",
        )
        assert schedule.item_id == 1
        assert schedule.start_on == date(2026, 11, 23)
        assert schedule.at_time == "18:45"
        assert schedule.amount == "0.5 tablet"


@pytest.mark.parametrize("width", (320, 390, 430, 760, 1024))
def test_733_mobile_edit_controls_are_tappable_and_expand_existing_forms(
    env, width,
):
    from playwright.sync_api import sync_playwright, expect

    client, _ = env
    seed(client)
    html = client.get("/regimen?day=2026-11-21").text
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": width, "height": 844})
            page.set_content(html)
            item_actions = page.locator("[data-reg733-item-actions]")
            expect(item_actions).to_have_count(2)
            schedule_actions = page.locator("[data-reg733-schedule-actions]")
            expect(schedule_actions).to_have_count(1)
            medication = item_actions.nth(0)
            supplement = item_actions.nth(1)
            # Template ordering follows kind (medication before supplement).
            med_trigger = medication.locator("summary[data-reg733-edit]")
            supp_trigger = supplement.locator("summary[data-reg733-edit]")
            schedule_trigger = schedule_actions.locator("summary[data-reg733-edit]")
            expect(med_trigger).to_have_text("Edit medication")
            expect(supp_trigger).to_have_text("Edit supplement")
            expect(schedule_trigger).to_have_text("Edit schedule")
            for trigger in (med_trigger, supp_trigger, schedule_trigger):
                assert trigger.evaluate(
                    "(node) => node.getBoundingClientRect().height >= 44"
                ), (width, trigger.text_content())
            med_editor = medication.locator('form[action="/regimen/items/1/edit"]')
            expect(med_editor).to_be_hidden()
            med_trigger.click()
            expect(med_editor).to_be_visible()
            expect(med_editor.locator('[name="name"]')).to_have_value("Example medication")
            expect(med_editor.locator('[name="strength"]')).to_have_value("20 mg")
            med_trigger.click()
            expect(med_editor).to_be_hidden()
            supp_editor = supplement.locator('form[action="/regimen/items/2/edit"]')
            supp_trigger.click()
            expect(supp_editor).to_be_visible()
            expect(supp_editor.locator('[name="name"]')).to_have_value("Example supplement")
            schedule_editor = schedule_actions.locator(
                'form[action="/regimen/schedules/1/edit"]'
            )
            schedule_trigger.click()
            expect(schedule_editor).to_be_visible()
            expect(schedule_editor.locator('[name="start_on"]')).to_have_value("2026-11-21")
            expect(schedule_editor.locator('[name="at_time"]')).to_have_value("08:30")
            assert page.evaluate(
                "document.documentElement.scrollWidth <= innerWidth"
            ), width
        finally:
            browser.close()
