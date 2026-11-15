"""Release 635: isolated HTTP + SQLite safety and schedule regressions."""
from datetime import date
from urllib.parse import urlencode

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.models import ChangeAudit, RegimenEntry, RegimenItem, RegimenSchedule
from app.routers import regimen635

pytestmark = pytest.mark.quick


@pytest.fixture
def env(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'regimen635.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    @event.listens_for(engine, "connect")
    def fk(connection, _):
        cur = connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    app = FastAPI()
    app.include_router(regimen635.router)
    def isolated():
        with Session() as db:
            yield db
    app.dependency_overrides[get_db] = isolated
    with TestClient(app, follow_redirects=False) as client:
        yield client, Session
    engine.dispose()


def post(client, route, data=None):
    response = client.post(
        route, content=urlencode(data or {}),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 303, response.text
    return response


def item(client, name="Vitamin X", kind="supplement"):
    result = post(client, "/regimen/items", {
        "name": name, "kind": kind, "strength": "1 mg",
        "purpose": "Personal tracking only",
    })
    assert "err=" not in result.headers["location"]


def schedule(client, item_id=1, **extra):
    values = dict(item_id=item_id, cadence="daily", start_on="2026-11-15",
                  amount="1 capsule", at_time="09:00", meal="breakfast")
    values.update(extra)
    return post(client, "/regimen/schedules", values)


def log(client, item_id=1, schedule_id="1", when="2026-11-15T09:12", **extra):
    values = dict(item_id=item_id, schedule_id=schedule_id, outcome="taken",
                  amount="1 capsule", meal="breakfast", logged_at=when)
    values.update(extra)
    return post(client, "/regimen/entries", values)


def test_catalog_schedule_actual_intake_and_audit(env):
    client, Session = env
    item(client)
    response = schedule(client)
    assert "err=" not in response.headers["location"]
    page = client.get("/regimen?day=2026-11-15")
    assert page.status_code == 200
    assert "Vitamin X" in page.text
    assert "Daily regimen" in page.text
    with Session() as db:
        assert len(list(db.scalars(select(RegimenEntry)))) == 0
    response = log(client)
    assert "err=" not in response.headers["location"]
    with Session() as db:
        entries = list(db.scalars(select(RegimenEntry)))
        assert len(entries) == 1
        assert entries[0].meal == "breakfast"
        assert entries[0].outcome == "taken"
        assert entries[0].amount == "1 capsule"
        audit_actions = [a.action for a in db.scalars(select(ChangeAudit))]
        assert audit_actions == ["create", "create", "create"]


def test_duplicate_scheduled_day_is_rejected_but_manual_is_allowed(env):
    client, Session = env
    item(client)
    schedule(client)
    log(client)
    response = log(client, when="2026-11-15T21:10")
    assert "err=" in response.headers["location"]
    response = log(client, schedule_id="", when="2026-11-15T21:10")
    assert "err=" not in response.headers["location"]
    with Session() as db:
        assert len(list(db.scalars(select(RegimenEntry)))) == 2


def test_skipped_due_schedule_does_not_mark_taken(env):
    client, Session = env
    item(client)
    schedule(client)
    response = log(client, outcome="skipped", amount="")
    assert "err=" not in response.headers["location"]
    with Session() as db:
        entry = db.scalar(select(RegimenEntry))
        assert entry.outcome == "skipped"
        assert entry.amount == ""


def test_schedule_calendar_rules_and_prn(env):
    client, Session = env
    item(client)
    schedule(client, cadence="weekly", weekdays="0,2,4")
    schedule(client, cadence="interval", interval_days="3")
    schedule(client, cadence="prn")
    with Session() as db:
        rows = list(db.scalars(select(RegimenSchedule).order_by(RegimenSchedule.id)))
        assert not regimen635.due_on(rows[0], date(2026, 11, 15))
        assert regimen635.due_on(rows[0], date(2026, 11, 16))
        assert regimen635.due_on(rows[1], date(2026, 11, 15))
        assert regimen635.due_on(rows[1], date(2026, 11, 18))
        assert not regimen635.due_on(rows[1], date(2026, 11, 16))
        assert not regimen635.due_on(rows[2], date(2026, 11, 15))


def test_bad_cadence_or_cross_item_schedule_rejected(env):
    client, Session = env
    item(client)
    item(client, "Other medicine", "medication")
    assert "err=" in schedule(client, cadence="weekly", weekdays="9").headers["location"]
    schedule(client)
    response = log(client, item_id=2, schedule_id="1")
    assert "err=" in response.headers["location"]
    with Session() as db:
        assert list(db.scalars(select(RegimenEntry))) == []


def test_intake_edit_delete_preserves_audit(env):
    client, Session = env
    item(client)
    schedule(client)
    log(client)
    response = post(client, "/regimen/entries/1/edit", {
        "item_id": "1", "schedule_id": "1",
        "logged_at": "2026-11-15T09:15", "outcome": "taken",
        "amount": "2 capsules", "meal": "dinner",
        "notes": "Corrected entry",
    })
    assert "err=" not in response.headers["location"]
    with Session() as db:
        entry = db.get(RegimenEntry, 1)
        assert entry.amount == "2 capsules"
        assert entry.meal == "dinner"
        assert db.scalar(select(ChangeAudit).where(
            ChangeAudit.entity_type == "regimen_entry",
            ChangeAudit.action == "edit",
        )) is not None
    post(client, "/regimen/entries/1/delete")
    with Session() as db:
        assert db.get(RegimenEntry, 1) is None
        assert db.scalar(select(ChangeAudit).where(
            ChangeAudit.entity_type == "regimen_entry",
            ChangeAudit.action == "delete",
        )) is not None


def test_archive_and_stop_preserve_records(env):
    client, Session = env
    item(client)
    schedule(client)
    log(client)
    post(client, "/regimen/schedules/1/stop")
    post(client, "/regimen/items/1/archive")
    with Session() as db:
        assert db.get(RegimenItem, 1).active is False
        assert db.get(RegimenSchedule, 1).active is False
        assert db.get(RegimenEntry, 1) is not None


def test_no_food_or_vial_tables_are_mutated(env):
    client, Session = env
    item(client)
    schedule(client)
    log(client)
    with Session() as db:
        from app.models import Vial, DoseLog
        assert list(db.scalars(select(Vial))) == []
        assert list(db.scalars(select(DoseLog))) == []


def test_regimen_page_and_models_are_present():
    from pathlib import Path
    from jinja2 import Environment
    root = Path(__file__).resolve().parents[1]
    template = (root / "app/templates/regimen635.html").read_text()
    Environment().parse(template)
    assert "Intake history" in template
    assert 'action="/regimen/entries"' in template
    assert "Meal (optional)" in template
    assert "No doses are recommended" in template or "No doses are recommended" in (
        root / "app/routers/regimen635.py"
    ).read_text()


def test_edit_catalog_and_schedule_are_audited(env):
    client, Session = env
    item(client)
    schedule(client)
    response = post(client, "/regimen/items/1/edit", {
        "kind": "medication", "name": "Corrected name",
        "strength": "2 mg", "active": "yes",
    })
    assert "err=" not in response.headers["location"]
    response = post(client, "/regimen/schedules/1/edit", {
        "cadence": "interval", "interval_days": "3",
        "start_on": "2026-11-15", "amount": "1 tablet",
        "meal": "", "active": "yes",
    })
    assert "err=" not in response.headers["location"]
    with Session() as db:
        assert db.get(RegimenItem, 1).kind == "medication"
        assert db.get(RegimenItem, 1).name == "Corrected name"
        assert db.get(RegimenSchedule, 1).cadence == "interval"
        assert db.get(RegimenSchedule, 1).interval_days == 3
        actions = [(a.entity_type, a.action) for a in db.scalars(select(ChangeAudit))]
        assert ("regimen_item", "edit") in actions
        assert ("regimen_schedule", "edit") in actions


def test_invalid_schedule_date_rejected_with_no_changes(env):
    client, Session = env
    item(client)
    assert "err=" in schedule(
        client, start_on="2026-11-15", end_on="2026-11-14",
    ).headers["location"]
    assert "err=" in schedule(
        client, cadence="interval", interval_days="0",
    ).headers["location"]
    with Session() as db:
        assert list(db.scalars(select(RegimenSchedule))) == []


def test_edit_does_not_allow_duplicate_schedule_on_same_day(env):
    client, Session = env
    item(client)
    schedule(client)
    log(client)
    log(client, schedule_id="", when="2026-11-15T18:00")
    response = post(client, "/regimen/entries/2/edit", {
        "item_id": "1", "schedule_id": "1",
        "logged_at": "2026-11-15T18:00",
        "outcome": "taken", "amount": "1 capsule", "meal": "",
    })
    assert "err=" in response.headers["location"]
    with Session() as db:
        assert db.get(RegimenEntry, 2).schedule_id is None
