"""Release 739: safe Workout routine and Saved Food MACD plus CSS/mobile parity.

All database fixtures are isolated and FK-enforced. No DEV/PROD data writes.
"""
import json
import re
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlencode

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jinja2 import Environment
from sqlalchemy import create_engine, event, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.models import ChangeAudit
from app.food_read_engine406 import get_food_read_engine406
from app.routers import food, food_bundle376, workouts655
from app.workout_models654 import WorkoutEquipment654, WorkoutSession654
from app.workout_models655 import (
    WorkoutRoutine655, WorkoutRoutineItem655, WorkoutSessionRoutine655,
)
from app.workout_models667 import WorkoutRoutineConfig667, WorkoutRoutineTarget667
from app.workout_models668 import (
    WorkoutRoutineSchedule668, WorkoutRoutineGroup668, WorkoutRoutineGroupMember668,
)

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "app/static/css"
TEMPLATES = ROOT / "app/templates"


@pytest.fixture
def gym(tmp_path):
    engine = create_engine(
        "sqlite:///" + str(tmp_path / "gym739.sqlite"),
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def enforce_fk(connection, _):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    app = FastAPI()
    app.include_router(workouts655.router)

    def scoped():
        with Session() as db:
            yield db

    app.dependency_overrides[get_db] = scoped
    with TestClient(app, follow_redirects=False) as client:
        yield client, Session
    engine.dispose()


@pytest.fixture
def pantry():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def enforce_fk(connection, _):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    app = FastAPI()
    app.include_router(food.router)
    app.dependency_overrides[get_food_read_engine406] = lambda: engine
    food_bundle376.init_schema(engine)
    with TestClient(app, follow_redirects=False) as client:
        yield client, engine
    engine.dispose()


def post(client, path, data=None):
    return client.post(
        path, content=urlencode(data or {}),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        follow_redirects=False,
    )


def new_routine(client, name="Upper body"):
    r = post(client, "/workouts/routines", {"name": name})
    assert r.status_code == 303
    assert r.headers["location"].startswith("/workouts/routines/")
    return int(r.headers["location"].split("?")[0].rstrip("/").split("/")[-1])


def new_food(engine, name="Banana"):
    with engine.begin() as db:
        result = db.execute(text("""
            INSERT INTO tracker_food_products
                (name,barcode,serving_description,nutrients,source)
            VALUES (:name,NULL,'1 serving',:nutrients,'manual')
        """), {"name": name, "nutrients": json.dumps({
            key: 0 for key in food.NUTRIENTS
        })})
        return result.lastrowid


def saved_version(client, product_id):
    page = client.get(f"/food/saved/{product_id}/edit?day=2026-11-21")
    assert page.status_code == 200
    found = re.search(r'name="version" value="([a-f0-9]{64})"', page.text)
    assert found, page.text[:600]
    return found.group(1), page.text


def test_739_rename_routine_preserves_id_order_and_audits(gym):
    client, Session = gym
    ident = new_routine(client)
    changed = post(client, f"/workouts/routines/{ident}/rename", {"name": "  Upper A  "})
    assert changed.status_code == 303 and "err=" not in changed.headers["location"]
    with Session() as db:
        assert db.get(WorkoutRoutine655, ident).name == "Upper A"
        edit = db.scalar(select(ChangeAudit).where(
            ChangeAudit.entity_type == "workout_routine",
            ChangeAudit.entity_id == ident,
            ChangeAudit.action == "edit",
        ))
        assert json.loads(edit.before_json)["name"] == "Upper body"
        assert json.loads(edit.after_json)["name"] == "Upper A"
    for value in ("", " " * 4, "x" * 121):
        denied = post(client, f"/workouts/routines/{ident}/rename", {"name": value})
        assert denied.status_code == 303 and "err=" in denied.headers["location"]
    with Session() as db:
        assert db.get(WorkoutRoutine655, ident).name == "Upper A"


def test_739_unused_routine_delete_is_confirmed_audited_and_scoped(gym):
    client, Session = gym
    doomed = new_routine(client, "Accidental routine")
    keep = new_routine(client, "Keep routine")
    not_confirmed = post(client, f"/workouts/routines/{doomed}/delete")
    assert "err=" in not_confirmed.headers["location"]
    with Session() as db:
        assert db.get(WorkoutRoutine655, doomed) is not None
    result = post(client, f"/workouts/routines/{doomed}/delete", {
        "confirm_delete": "delete",
    })
    assert result.status_code == 303 and "err=" not in result.headers["location"]
    with Session() as db:
        assert db.get(WorkoutRoutine655, doomed) is None
        assert db.get(WorkoutRoutine655, keep) is not None
        change = db.scalar(select(ChangeAudit).where(
            ChangeAudit.entity_type == "workout_routine",
            ChangeAudit.entity_id == doomed,
            ChangeAudit.action == "delete",
        ))
        assert json.loads(change.before_json)["name"] == "Accidental routine"
    missing = post(client, f"/workouts/routines/{doomed}/delete", {
        "confirm_delete": "delete",
    })
    assert missing.status_code == 404


def test_739_unused_routine_delete_cleans_planning_not_equipment(gym):
    client, Session = gym
    ident = new_routine(client)
    with Session() as db:
        machine = WorkoutEquipment654(name="Nautilus row", kind="selectorized")
        db.add(machine)
        db.flush()
        item = WorkoutRoutineItem655(
            routine_id=ident, equipment_id=machine.id, position=0,
        )
        db.add(item)
        db.flush()
        group = WorkoutRoutineGroup668(
            routine_id=ident, group_name="Pair", group_type="superset", rounds=3,
        )
        db.add(group)
        db.flush()
        db.add(WorkoutRoutineGroupMember668(
            group_id=group.id, routine_item_id=item.id, position=0,
        ))
        db.add(WorkoutRoutineTarget667(routine_item_id=item.id))
        db.add(WorkoutRoutineConfig667(routine_id=ident, rest_seconds=90))
        db.add(WorkoutRoutineSchedule668(
            routine_id=ident, weekdays="0,2,4", start_on=date(2026, 11, 21),
        ))
        machine_id, item_id, group_id = machine.id, item.id, group.id
        db.commit()
    result = post(client, f"/workouts/routines/{ident}/delete", {
        "confirm_delete": "delete",
    })
    assert result.status_code == 303 and "err=" not in result.headers["location"]
    with Session() as db:
        for model, key in (
            (WorkoutRoutine655, ident),
            (WorkoutRoutineItem655, item_id),
            (WorkoutRoutineTarget667, item_id),
            (WorkoutRoutineGroup668, group_id),
            (WorkoutRoutineConfig667, ident),
            (WorkoutRoutineSchedule668, ident),
        ):
            assert db.get(model, key) is None, model.__name__
        assert list(db.scalars(select(WorkoutRoutineGroupMember668))) == []
        assert db.get(WorkoutEquipment654, machine_id) is not None
        audit = db.scalar(select(ChangeAudit).where(
            ChangeAudit.entity_type == "workout_routine",
            ChangeAudit.entity_id == ident, ChangeAudit.action == "delete",
        ))
        assert json.loads(audit.before_json)["exercises_deleted"] == 1


def test_739_routine_with_history_must_not_delete_or_unlink(gym):
    client, Session = gym
    ident = new_routine(client)
    with Session() as db:
        session = WorkoutSession654(
            started_at=datetime(2026, 11, 19, 10, 0),
            completed_at=datetime(2026, 11, 19, 11, 0),
        )
        db.add(session)
        db.flush()
        db.add(WorkoutSessionRoutine655(session_id=session.id, routine_id=ident))
        session_id = session.id
        db.commit()
    page = client.get(f"/workouts/routines/{ident}")
    assert page.status_code == 200
    assert "deletion unavailable" in page.text
    assert f'action="/workouts/routines/{ident}/delete"' not in page.text
    forged = post(client, f"/workouts/routines/{ident}/delete", {
        "confirm_delete": "delete",
    })
    assert forged.status_code == 303 and "err=" in forged.headers["location"]
    with Session() as db:
        assert db.get(WorkoutRoutine655, ident) is not None
        assert db.get(WorkoutSessionRoutine655, session_id).routine_id == ident


def test_739_routine_index_and_detail_offer_consistent_macd(gym):
    client, _ = gym
    rid = new_routine(client)
    index = client.get("/workouts/routines")
    detail = client.get(f"/workouts/routines/{rid}")
    assert index.status_code == detail.status_code == 200
    for html in (index.text, detail.text):
        assert f'action="/workouts/routines/{rid}/rename"' in html
        assert f'action="/workouts/routines/{rid}/delete"' in html
        assert f'action="/workouts/routines/{rid}/duplicate"' in html
        assert 'name="confirm_delete" value="delete"' in html
        assert 'Edit routine</summary>' in html
        assert 'Delete routine</button>' in html
        assert html.count("tracker-workout-routines739.css?v=739") == 1
        assert 'tracker-workouts655.css?v=655' not in html


def test_739_unlinked_saved_food_delete_requires_version_confirmation(pantry):
    client, engine = pantry
    target = new_food(engine, "Accidental saved item")
    untouched = new_food(engine, "Keep saved item")
    with engine.begin() as db:
        db.execute(text(
            "INSERT INTO tracker_food_favorites(product_id) VALUES (:id)"
        ), {"id": target})
    version, page = saved_version(client, target)
    assert f'action="/food/saved/{target}/delete"' in page
    assert f'form="food739-delete-{target}"' in page
    assert 'Delete Saved Food' in page
    no_confirm = post(client, f"/food/saved/{target}/delete", {
        "day": "2026-11-21", "version": version,
    })
    assert no_confirm.status_code == 422
    stale = post(client, f"/food/saved/{target}/delete", {
        "day": "2026-11-21", "version": "0" * 64,
        "confirm_delete": "delete",
    })
    assert stale.status_code == 409
    deleted = post(client, f"/food/saved/{target}/delete", {
        "day": "2026-11-21", "version": version,
        "confirm_delete": "delete",
    })
    assert deleted.status_code == 303
    assert deleted.headers["location"] == "/food?day=2026-11-21#food-search"
    with engine.connect() as db:
        assert db.execute(text(
            "SELECT COUNT(*) FROM tracker_food_products WHERE id=:id"
        ), {"id": target}).scalar_one() == 0
        assert db.execute(text(
            "SELECT COUNT(*) FROM tracker_food_favorites WHERE product_id=:id"
        ), {"id": target}).scalar_one() == 0
        assert db.execute(text(
            "SELECT COUNT(*) FROM tracker_food_products WHERE id=:id"
        ), {"id": untouched}).scalar_one() == 1
    assert client.get(f"/food/saved/{target}/edit?day=2026-11-21").status_code == 404


def test_739_saved_food_history_and_templates_protected_even_on_forgery(pantry):
    client, engine = pantry
    used = new_food(engine, "Logged meal")
    templated = new_food(engine, "Template ingredient")
    with engine.begin() as db:
        db.execute(text("""
            INSERT INTO tracker_food_entries(product_id,eaten_on,meal,servings)
            VALUES (:id, '2026-11-21','Snack',1)
        """), {"id": used})
        template_id = db.execute(text("""
            INSERT INTO tracker_food_meal_templates(name) VALUES ('Snack template')
        """)).lastrowid
        db.execute(text("""
            INSERT INTO tracker_food_meal_template_items
                (template_id, product_id, servings, meal)
            VALUES (:template_id, :id, 1, 'Snack')
        """), {"template_id": template_id, "id": templated})
    for ident in (used, templated):
        version, page = saved_version(client, ident)
        assert f'action="/food/saved/{ident}/delete"' not in page
        assert 'data-food739-delete-blocked' in page
        denied = post(client, f"/food/saved/{ident}/delete", {
            "day": "2026-11-21", "version": version,
            "confirm_delete": "delete",
        })
        assert denied.status_code == 409
        with engine.connect() as db:
            assert db.execute(text(
                "SELECT COUNT(*) FROM tracker_food_products WHERE id=:id"
            ), {"id": ident}).scalar_one() == 1


def test_739_routine_css_consolidates_legacy_assets_in_original_order():
    original = (
        (CSS / "tracker-workouts655.css").read_text().rstrip() + "\n"
        + (CSS / "tracker-workout-routine-alignment714.css").read_text().rstrip() + "\n"
    )
    merged = (CSS / "tracker-workout-routines739.css").read_text()
    assert merged.startswith(original)
    assert "Release 739" in merged[len(original):]
    for path in ("workout_routines655.html", "workout_routine_detail655.html"):
        source = (TEMPLATES / path).read_text()
        Environment().parse(source)
        assert source.count("tracker-workout-routines739.css?v=739") == 1
        assert "tracker-workouts655.css?v=655" not in source
        assert "tracker-workout-routine-alignment714.css?v=714" not in source


@pytest.mark.parametrize("width", [320, 390, 760, 1024])
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_739_routine_mobile_controls_and_native_edit_markers(gym, width, scheme):
    from playwright.sync_api import expect, sync_playwright
    client, _ = gym
    ident = new_routine(client)
    page_html = client.get("/workouts/routines").text
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page(
                viewport={"width": width, "height": 844},
                color_scheme=scheme,
            )
            page.set_content(page_html)
            page.add_style_tag(content=(ROOT / "app/static/app.css").read_text())
            page.add_style_tag(content=(
                CSS / "tracker-workouts654.css"
            ).read_text())
            page.add_style_tag(content=(
                CSS / "tracker-workout-routines739.css"
            ).read_text())
            panel = page.locator(".workout739-edit-panel")
            summary = panel.locator("summary")
            delete = page.locator(
                f'form[action="/workouts/routines/{ident}/delete"] > button'
            )
            expect(summary).to_be_visible()
            expect(delete).to_be_visible()
            assert summary.evaluate("el => getComputedStyle(el).display == 'list-item'")
            assert summary.evaluate("el => el.getBoundingClientRect().height >= 44")
            assert delete.evaluate("el => el.getBoundingClientRect().height >= 44")
            assert not panel.evaluate("el => el.open")
            summary.click()
            assert panel.evaluate("el => el.open")
            expect(panel.locator('input[name="name"]')).to_be_visible()
            assert page.evaluate(
                "document.documentElement.scrollWidth <= innerWidth + 1"
            ), (width, scheme)
        finally:
            browser.close()


@pytest.mark.parametrize("width", [320, 390, 760, 1024])
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_739_saved_food_delete_action_stays_visible_without_mobile_overflow(
    pantry, width, scheme,
):
    from playwright.sync_api import expect, sync_playwright
    client, engine = pantry
    ident = new_food(engine)
    page_html = client.get(f"/food/saved/{ident}/edit?day=2026-11-21").text
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page(
                viewport={"width": width, "height": 844},
                color_scheme=scheme,
            )
            page.set_content(page_html)
            page.add_style_tag(content=(ROOT / "app/static/app.css").read_text())
            page.add_style_tag(content=(
                ROOT / "app/static/css/tracker-saved-food-actions702.css"
            ).read_text())
            save = page.locator('.tracker-food-editor-actions702 > button.primary')
            delete = page.locator('.tracker-food-editor-delete739')
            form = page.locator(f'#food739-delete-{ident}')
            expect(save).to_be_visible()
            expect(delete).to_be_visible()
            assert form.get_attribute("action") == f"/food/saved/{ident}/delete"
            assert form.get_attribute("method") == "post"
            assert delete.get_attribute("form") == f"food739-delete-{ident}"
            assert save.evaluate("el => el.getBoundingClientRect().height >= 44")
            assert delete.evaluate("el => el.getBoundingClientRect().height >= 44")
            assert page.evaluate(
                "document.documentElement.scrollWidth <= innerWidth + 1"
            ), (width, scheme)
        finally:
            browser.close()
