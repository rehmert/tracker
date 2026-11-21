"""Release 732: delete a medication without orphaned regimen records.

All tests use disposable SQLite with foreign-key enforcement.
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
    RegimenProductFacts639, RegimenTabletSchedule731, RegimenTabletEntry731,
)
from app.routers import regimen635

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def env(tmp_path):
    engine = create_engine(
        "sqlite:///" + str(tmp_path / "delete732.sqlite"),
        connect_args={"check_same_thread": False},
    )
    @event.listens_for(engine, "connect")
    def fk(connection, _):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
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


def post(client, route, fields=None):
    response = client.post(
        route,
        content=urlencode(fields or {}),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 303, response.text
    return response


def create_item(client, name, kind="medication", *, facts=False):
    fields = {"name": name, "kind": kind, "strength": "20 mg", "form": "Tablet"}
    if facts:
        fields["label_facts_json"] = json.dumps({
            "brand": "Example Brand", "source": "manual",
            "source_id": "", "ingredients": [],
        })
    result = post(client, "/regimen/items", fields)
    assert "err=" not in result.headers["location"]


def create_tablet_schedule(client, item_id=1):
    result = post(client, "/regimen/schedules", {
        "item_id": str(item_id), "cadence": "daily", "start_on": "2026-11-21",
        "tablet_mode": "tablet", "tablet_strength_mg": "20",
        "prescribed_dose_mg": "10", "tablets_planned": "0.5", "meal": "",
    })
    assert "err=" not in result.headers["location"]


def create_tablet_intake(client, item_id=1, schedule_id=1):
    result = post(client, "/regimen/entries", {
        "item_id": str(item_id), "schedule_id": str(schedule_id),
        "outcome": "taken", "logged_at": "2026-11-21T09:30",
        "tablet_mode": "tablet", "tablet_count": "0.5",
        "meal": "",
    })
    assert "err=" not in result.headers["location"]


def test_732_delete_without_dependents_and_double_confirmation(env):
    client, Session = env
    create_item(client, "Accidentally added medication")
    no_confirmation = post(client, "/regimen/items/1/delete")
    assert "err=" in no_confirmation.headers["location"]
    with Session() as db:
        assert db.get(RegimenItem, 1) is not None
    yes = post(client, "/regimen/items/1/delete", {"confirm_delete": "delete"})
    assert "err=" not in yes.headers["location"]
    with Session() as db:
        assert db.get(RegimenItem, 1) is None
        deleted = list(db.scalars(select(ChangeAudit).where(
            ChangeAudit.entity_type == "regimen_item",
            ChangeAudit.action == "delete",
        )))
        assert len(deleted) == 1
        prior = json.loads(deleted[0].before_json)
        assert prior["name"] == "Accidentally added medication"
        assert prior["schedules_deleted"] == 0
        assert prior["intakes_deleted"] == 0
    # A missing record must never be a successful second deletion.
    assert client.post("/regimen/items/1/delete",
                       data={"confirm_delete": "delete"}).status_code == 404


def test_732_delete_with_schedules_history_tablets_and_label_facts(env):
    client, Session = env
    create_item(client, "Example medication", facts=True)
    create_tablet_schedule(client)
    create_tablet_intake(client)
    create_item(client, "Keep unrelated supplement", "supplement")
    post(client, "/regimen/schedules", {
        "item_id": "2", "cadence": "daily", "start_on": "2026-11-21",
        "amount": "1 capsule", "meal": "",
    })
    post(client, "/regimen/entries", {
        "item_id": "2", "schedule_id": "2", "outcome": "taken",
        "logged_at": "2026-11-21T08:30", "amount": "1 capsule", "meal": "",
    })
    with Session() as db:
        assert db.get(RegimenProductFacts639, 1) is not None
        assert db.get(RegimenTabletSchedule731, 1) is not None
        assert db.get(RegimenTabletEntry731, 1) is not None

    deleted = post(client, "/regimen/items/1/delete", {
        "confirm_delete": "delete",
    })
    assert "err=" not in deleted.headers["location"]
    with Session() as db:
        assert db.get(RegimenItem, 1) is None
        assert db.get(RegimenSchedule, 1) is None
        assert db.get(RegimenEntry, 1) is None
        assert db.get(RegimenTabletSchedule731, 1) is None
        assert db.get(RegimenTabletEntry731, 1) is None
        assert list(db.scalars(select(RegimenProductFacts639).where(
            RegimenProductFacts639.item_id == 1,
        ))) == []
        assert db.get(RegimenItem, 2).name == "Keep unrelated supplement"
        assert db.get(RegimenSchedule, 2) is not None
        assert db.get(RegimenEntry, 2) is not None
        audits = list(db.scalars(select(ChangeAudit).where(
            ChangeAudit.action == "delete",
        )))
        kinds = {audit.entity_type for audit in audits}
        assert {
            "regimen_item", "regimen_schedule", "regimen_entry",
            "regimen_product_facts", "regimen_tablet_schedule",
            "regimen_tablet_entry",
        } <= kinds
        medication_delete = next(a for a in audits if a.entity_type == "regimen_item")
        before = json.loads(medication_delete.before_json)
        assert before["schedules_deleted"] == 1
        assert before["intakes_deleted"] == 1
        assert before["product_facts_deleted"] is True


def test_732_supplements_cannot_use_medication_delete_route(env):
    client, Session = env
    create_item(client, "Unrelated supplement", "supplement")
    response = post(client, "/regimen/items/1/delete", {
        "confirm_delete": "delete",
    })
    assert "err=" in response.headers["location"]
    with Session() as db:
        assert db.get(RegimenItem, 1) is not None


def test_732_bad_cross_item_schedule_references_block_delete(env):
    client, Session = env
    create_item(client, "To be deleted")
    create_item(client, "Other medication")
    create_tablet_schedule(client)
    # Reproduce a malformed legacy cross-item schedule reference.
    with Session() as db:
        db.add(RegimenEntry(
            item_id=2, schedule_id=1,
            logged_at=__import__("datetime").datetime(2026, 11, 21, 8),
            outcome="taken", amount="1 tablet", meal="", notes="",
        ))
        db.commit()
    blocked = post(client, "/regimen/items/1/delete", {
        "confirm_delete": "delete",
    })
    assert "err=" in blocked.headers["location"]
    with Session() as db:
        assert db.get(RegimenItem, 1) is not None
        assert db.get(RegimenItem, 2) is not None
        assert db.get(RegimenSchedule, 1) is not None
        assert db.scalar(select(RegimenEntry).where(
            RegimenEntry.item_id == 2,
        )) is not None


def test_732_archived_medications_can_still_be_deleted(env):
    client, Session = env
    create_item(client, "Archived mistaken medication")
    post(client, "/regimen/items/1/archive")
    with Session() as db:
        assert db.get(RegimenItem, 1).active is False
    deleted = post(client, "/regimen/items/1/delete", {
        "confirm_delete": "delete",
    })
    assert "err=" not in deleted.headers["location"]
    with Session() as db:
        assert db.get(RegimenItem, 1) is None


def test_732_live_regimen_form_shows_visible_delete_and_dependency_counts(env):
    template = (ROOT / "app/templates/regimen635.html").read_text()
    Environment().parse(template)
    client, Session = env
    create_item(client, "Example medication")
    create_tablet_schedule(client)
    create_tablet_intake(client)
    create_item(client, "Supplement", "supplement")
    response = client.get("/regimen?day=2026-11-21")
    assert response.status_code == 200
    html = response.text
    assert 'action="/regimen/items/1/delete"' in html
    assert 'action="/regimen/items/2/delete"' not in html
    assert "Delete medication" in html
    assert "1 schedule(s), and 1 intake record(s)" in html
    assert 'name="confirm_delete" value="delete"' in html
    assert "This cannot be undone" in html
    assert 'data-reg732-item-actions' in html
    # No delete on GET. Page is a read-only catalogue view.
    with Session() as db:
        assert db.get(RegimenItem, 1) is not None
        assert db.get(RegimenEntry, 1) is not None
