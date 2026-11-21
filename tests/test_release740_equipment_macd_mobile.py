"""Release 740: scoped Workout equipment MACD, historical dependency guards and mobile CSS.

Uses disposable per-test SQLite FK-ON DB. No installed DEV/PROD data.
"""
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jinja2 import Environment
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.models import ChangeAudit
from app.routers import workouts654
from app.workout_models654 import WorkoutEquipment654, WorkoutSession654, WorkoutSet654
from app.workout_models655 import WorkoutRoutine655, WorkoutRoutineItem655
from app.workout_models667 import WorkoutSessionTarget667
from app.workout_models668 import WorkoutEquipmentLoad668

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "app/static/css"
TEMPLATE = ROOT / "app/templates/workouts654.html"


@pytest.fixture
def env(tmp_path):
    engine = create_engine(
        "sqlite:///" + str(tmp_path / "workout740.sqlite"),
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        cur = connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    app = FastAPI()
    app.include_router(workouts654.router)

    def scoped():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = scoped
    with TestClient(app, follow_redirects=False) as client:
        yield client, Session
    engine.dispose()


def post(client, route, data=None):
    return client.post(
        route, content=urlencode(data or {}),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )


def add_equipment(client, Session, name="Nautilus Leg Press"):
    response = post(client, "/workouts/equipment", {
        "name": name, "gym": "Merritt Eldersburg",
        "kind": "selectorized", "manufacturer": "Nautilus",
        "model": "Equipment",
        "seat_setting": "2", "setup_notes": "Check seat",
    })
    assert response.status_code == 303
    assert "err=" not in response.headers["location"]
    with Session() as db:
        return db.scalar(select(WorkoutEquipment654.id).where(
            WorkoutEquipment654.name == name
        ))


def equipment_version(client, ident):
    page = client.get(f"/workouts?machine={ident}")
    assert page.status_code == 200
    match = re.search(
        rf'action="/workouts/equipment/{ident}/edit"[^>]*>.*?'
        rf'name="version" value="([0-9a-f]{{64}})"',
        page.text,
        re.DOTALL,
    )
    assert match, page.text[:900]
    return match.group(1), page.text


def test_740_equipment_edit_updates_identifiers_and_preserves_history_fields(env):
    client, Session = env
    ident = add_equipment(client, Session)
    with Session() as db:
        item = db.get(WorkoutEquipment654, ident)
        item.qr_value = "retired-qr-740"
        db.commit()
    version, html = equipment_version(client, ident)
    assert 'Edit equipment</summary>' in html
    assert f'action="/workouts/equipment/{ident}/edit"' in html
    changed = post(client, f"/workouts/equipment/{ident}/edit", {
        "version": version, "name": "  New Leg Press  ",
        "gym": "  Upstairs  ", "manufacturer": "  Nautilus  ", "model": "  NX  ",
    })
    assert changed.status_code == 303
    assert "err=" not in changed.headers["location"]
    with Session() as db:
        machine = db.get(WorkoutEquipment654, ident)
        assert (machine.name, machine.gym, machine.manufacturer, machine.model) == (
            "New Leg Press", "Upstairs", "Nautilus", "NX"
        )
        assert (machine.kind, machine.qr_value, machine.seat_setting, machine.setup_notes) == (
            "selectorized", "retired-qr-740", "2", "Check seat"
        )
        audit = db.scalar(select(ChangeAudit).where(
            ChangeAudit.entity_type == "workout_equipment",
            ChangeAudit.entity_id == ident,
            ChangeAudit.action == "edit",
        ))
        assert json.loads(audit.before_json)["name"] == "Nautilus Leg Press"
        assert json.loads(audit.after_json)["name"] == "New Leg Press"


@pytest.mark.parametrize("patch", [
    {"name": ""},
    {"name": "X" * 141},
    {"gym": ""},
    {"gym": "x" * 141},
    {"manufacturer": "M" * 101},
    {"model": "M" * 141},
])
def test_740_invalid_edits_do_not_modify_machine(env, patch):
    client, Session = env
    ident = add_equipment(client, Session)
    version, _ = equipment_version(client, ident)
    payload = {
        "version": version, "name": "Nautilus Leg Press",
        "gym": "Merritt Eldersburg", "manufacturer": "Nautilus", "model": "Equipment",
        **patch,
    }
    denied = post(client, f"/workouts/equipment/{ident}/edit", payload)
    assert denied.status_code == 303 and "err=" in denied.headers["location"]
    with Session() as db:
        item = db.get(WorkoutEquipment654, ident)
        assert item.name == "Nautilus Leg Press" and item.gym == "Merritt Eldersburg"


def test_740_stale_version_and_missing_equipment_fail_closed(env):
    client, Session = env
    ident = add_equipment(client, Session)
    old, _ = equipment_version(client, ident)
    update = {
        "version": old, "name": "Edited", "gym": "Merritt",
        "manufacturer": "", "model": "",
    }
    assert "err=" not in post(client, f"/workouts/equipment/{ident}/edit", update).headers["location"]
    stale = post(client, f"/workouts/equipment/{ident}/edit", {**update, "name": "Stale"})
    assert "err=" in stale.headers["location"]
    denied = post(client, f"/workouts/equipment/{ident}/delete", {
        "version": old, "confirm_delete": "delete",
    })
    assert "err=" in denied.headers["location"]
    with Session() as db:
        assert db.get(WorkoutEquipment654, ident).name == "Edited"
    assert post(client, "/workouts/equipment/999999/edit", update).status_code == 404
    assert post(client, "/workouts/equipment/999999/delete", {
        "version": old, "confirm_delete": "delete",
    }).status_code == 404


def test_740_confirmed_unused_equipment_delete_cleans_only_metadata(env):
    client, Session = env
    ident = add_equipment(client, Session)
    survivor = add_equipment(client, Session, "Nautilus Row")
    with Session() as db:
        db.add(WorkoutEquipmentLoad668(
            equipment_id=ident, load_mode="stack", multiplier=1, offset_lb=0,
            note="Empty machine calibration",
        ))
        db.commit()
    version, html = equipment_version(client, ident)
    assert f'action="/workouts/equipment/{ident}/delete"' in html
    assert "Delete equipment</button>" in html
    missing_confirmation = post(client, f"/workouts/equipment/{ident}/delete", {
        "version": version,
    })
    assert "err=" in missing_confirmation.headers["location"]
    with Session() as db:
        assert db.get(WorkoutEquipment654, ident) is not None
    deleted = post(client, f"/workouts/equipment/{ident}/delete", {
        "version": version, "confirm_delete": "delete",
    })
    assert deleted.status_code == 303
    assert "err=" not in deleted.headers["location"]
    with Session() as db:
        assert db.get(WorkoutEquipment654, ident) is None
        assert db.get(WorkoutEquipmentLoad668, ident) is None
        assert db.get(WorkoutEquipment654, survivor) is not None
        audit = db.scalar(select(ChangeAudit).where(
            ChangeAudit.entity_type == "workout_equipment",
            ChangeAudit.entity_id == ident,
            ChangeAudit.action == "delete",
        ))
        assert json.loads(audit.before_json)["name"] == "Nautilus Leg Press"
    assert post(client, f"/workouts/equipment/{ident}/delete", {
        "version": version, "confirm_delete": "delete",
    }).status_code == 404


@pytest.mark.parametrize("used_by", ["set", "routine", "target"])
def test_740_historically_linked_equipment_cannot_delete_even_by_forged_post(env, used_by):
    client, Session = env
    ident = add_equipment(client, Session)
    with Session() as db:
        if used_by == "set":
            session = WorkoutSession654(
                started_at=datetime(2026, 11, 21, 10),
                completed_at=datetime(2026, 11, 21, 11),
            )
            db.add(session)
            db.flush()
            db.add(WorkoutSet654(
                session_id=session.id, equipment_id=ident,
                weight_lb=50, reps=10,
            ))
        elif used_by == "routine":
            routine = WorkoutRoutine655(name="Keep routine")
            db.add(routine)
            db.flush()
            db.add(WorkoutRoutineItem655(
                routine_id=routine.id, equipment_id=ident, position=0
            ))
        else:
            session = WorkoutSession654(
                started_at=datetime(2026, 11, 21, 10),
                completed_at=datetime(2026, 11, 21, 11),
            )
            db.add(session)
            db.flush()
            db.add(WorkoutSessionTarget667(
                session_id=session.id, equipment_id=ident,
                target_sets=3, target_reps=12, target_weight_lb=60,
                rest_seconds=90, setup_note="",
            ))
        db.commit()
    version, html = equipment_version(client, ident)
    assert "data-workout740-linked" in html
    assert f'action="/workouts/equipment/{ident}/delete"' not in html
    assert 'title="Equipment referenced' in html
    blocked = post(client, f"/workouts/equipment/{ident}/delete", {
        "version": version, "confirm_delete": "delete",
    })
    assert blocked.status_code == 303 and "err=" in blocked.headers["location"]
    with Session() as db:
        assert db.get(WorkoutEquipment654, ident) is not None
        if used_by == "set":
            assert list(db.scalars(select(WorkoutSet654)))
        elif used_by == "routine":
            assert list(db.scalars(select(WorkoutRoutineItem655)))
        else:
            assert list(db.scalars(select(WorkoutSessionTarget667)))


def test_740_legacy_equipment_settings_and_recording_routes_stay_intact(env):
    client, Session = env
    ident = add_equipment(client, Session)
    response = post(client, f"/workouts/equipment/{ident}/settings", {
        "seat_setting": "4", "setup_notes": "Seat adjusted",
    })
    assert response.status_code == 303
    with Session() as db:
        item = db.get(WorkoutEquipment654, ident)
        assert (item.seat_setting, item.setup_notes) == ("4", "Seat adjusted")
    assert post(client, "/workouts/start").status_code == 303
    assert post(client, "/workouts/sets", {
        "equipment_id": ident, "weight_lb": 50, "reps": 10,
    }).status_code == 303
    with Session() as db:
        assert db.scalar(select(WorkoutSet654.equipment_id)) == ident


def test_740_equipment_css_merge_preserves_previous_rule_order():
    original = (
        (CSS / "tracker-workouts654.css").read_text().rstrip() + "\n"
        + (CSS / "tracker-workouts655.css").read_text().rstrip() + "\n"
    )
    merged = (CSS / "tracker-workout-equipment740.css").read_text()
    assert merged.startswith(original)
    assert "Release 740" in merged[len(original):]
    src = TEMPLATE.read_text()
    Environment().parse(src)
    assert src.count("tracker-workout-equipment740.css?v=740") == 1
    assert "tracker-workouts654.css?v=654" not in src
    assert "tracker-workouts655.css?v=655" not in src
    assert src.index("tracker-workout-equipment740.css?v=740") < src.index(
        "tracker-workouts656.css?v=692"
    )


@pytest.mark.parametrize("width", [320, 390, 760, 1024])
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_740_mobile_equipment_edit_delete_actions_and_no_overflow(env, width, scheme):
    from playwright.sync_api import expect, sync_playwright
    client, Session = env
    ident = add_equipment(client, Session)
    html = client.get(f"/workouts?machine={ident}").text
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page(
                viewport={"width": width, "height": 844}, color_scheme=scheme
            )
            page.set_content(html)
            page.add_style_tag(content=(ROOT / "app/static/app.css").read_text())
            page.add_style_tag(content=(CSS / "tracker-workout-equipment740.css").read_text())
            machine = page.locator(f"#workout-machine-{ident}")
            assert machine.get_attribute("open") is not None
            toolbar = machine.locator("[data-workout740-equipment-actions]")
            summary = toolbar.locator("summary.workout740-action")
            delete = toolbar.locator('form[action$="/delete"] > button')
            expect(summary).to_be_visible()
            expect(delete).to_be_visible()
            assert summary.evaluate("el => getComputedStyle(el).display == 'list-item'")
            assert summary.evaluate("el => el.getBoundingClientRect().height >= 44")
            assert delete.evaluate("el => el.getBoundingClientRect().height >= 44")
            summary.click()
            form = toolbar.locator(f'form[action="/workouts/equipment/{ident}/edit"]')
            expect(form.locator('input[name="name"]')).to_be_visible()
            assert form.locator('input[name="name"]').input_value() == "Nautilus Leg Press"
            assert page.evaluate(
                "document.documentElement.scrollWidth <= innerWidth + 1"
            ), (width, scheme)
        finally:
            browser.close()


@pytest.mark.parametrize("width", [320, 390, 760, 1024])
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_740_equipment_css_original_cascade_still_matches_merged_prefix(width, scheme):
    from playwright.sync_api import sync_playwright
    original = (
        (CSS / "tracker-workouts654.css").read_text().rstrip() + "\n"
        + (CSS / "tracker-workouts655.css").read_text().rstrip() + "\n"
    )
    combined = (CSS / "tracker-workout-equipment740.css").read_text()
    fixture = (
        '<html><head><meta name="viewport" content="width=device-width,initial-scale=1">'
        '<style id="subject"></style></head><body>'
        '<div class="workout654"><div class="workout-routine-strip655">'
        '<div class="workout-routine-title655"><h2>Routines</h2></div>'
        '<div class="workout-routine-launch655"><form><button>Start</button></form></div>'
        '</div><details class="workout-machine654"><summary>Machine</summary>'
        '<form class="workout-grid654"><label>Load<input></label>'
        '<button>Record</button></form></details></div></body></html>'
    )
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page(viewport={"width": width, "height": 844},
                                    color_scheme=scheme)
            page.set_content(fixture)
            def snapshot(css):
                page.locator("#subject").evaluate(
                    "(el, value) => el.textContent = value", css
                )
                return page.locator(".workout654, .workout-machine654, .workout-grid654, .workout-routine-strip655").evaluate_all(
                    """els => els.map(el => {
                        const v = getComputedStyle(el);
                        return [v.display, v.gap, v.padding, v.gridTemplateColumns];
                    })"""
                )
            assert snapshot(original) == snapshot(combined), (width, scheme)
        finally:
            browser.close()
