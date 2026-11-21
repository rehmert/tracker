"""Release 731: fractional tablets, prescribed doses, and historical snapshots.

All writes use disposable SQLite. No internet, existing user files or PROD.
"""
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlencode

from jinja2 import Environment

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker

from app.db import Base, get_db
from app.models import (
    ChangeAudit, RegimenItem, RegimenSchedule, RegimenEntry,
    RegimenTabletSchedule731, RegimenTabletEntry731,
)
from app.regimen_tablets731 import (
    amount, catalog_tablet_strength, entry_values, schedule_values,
)
from app.routers import regimen635


@pytest.fixture
def env(tmp_path):
    engine = create_engine(
        "sqlite:///" + str(tmp_path / "tablet731.sqlite"),
        connect_args={"check_same_thread": False},
    )
    @event.listens_for(engine, "connect")
    def foreign_keys(connection, _):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    api = FastAPI()
    api.include_router(regimen635.router)
    def override():
        with Session() as db:
            yield db
    api.dependency_overrides[get_db] = override
    with TestClient(api, follow_redirects=False) as client:
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


def make_item(client, *, name="Example tablet", kind="medication"):
    response = post(client, "/regimen/items", {
        "name": name, "kind": kind, "strength": "20 mg", "form": "Tablet",
    })
    assert "err=" not in response.headers["location"]


def plan_fields(**overrides):
    result = dict(
        item_id="1", cadence="daily", start_on="2026-11-21",
        tablet_mode="tablet", tablet_strength_mg="20",
        prescribed_dose_mg="10", tablets_planned="0.5", meal="",
    )
    result.update(overrides)
    return result


def intake_fields(**overrides):
    result = dict(
        item_id="1", schedule_id="1", outcome="taken",
        logged_at="2026-11-21T09:30", tablet_mode="tablet",
        tablet_count="0.5", meal="", notes="Doctor ordered split tablet",
    )
    result.update(overrides)
    return result


def test_731_half_tablet_schedule_actual_history_and_dose_change(env):
    client, Session = env
    make_item(client)
    created = post(client, "/regimen/schedules", plan_fields())
    assert "err=" not in created.headers["location"]
    with Session() as db:
        schedule = db.get(RegimenSchedule, 1)
        plan = db.get(RegimenTabletSchedule731, 1)
        assert schedule.amount == "0.5 tablets (10 mg)"
        assert plan.tablet_strength_mg == Decimal("20")
        assert plan.prescribed_dose_mg == Decimal("10")
        assert plan.tablets_planned == Decimal("0.5")
    logged = post(client, "/regimen/entries", intake_fields())
    assert "err=" not in logged.headers["location"]
    with Session() as db:
        actual = db.get(RegimenEntry, 1)
        snapshot = db.get(RegimenTabletEntry731, 1)
        assert actual.amount == "0.5 tablets (10 mg)"
        assert snapshot.tablets_taken == Decimal("0.5")
        assert snapshot.administered_dose_mg == Decimal("10")
        assert snapshot.prescribed_dose_mg == Decimal("10")
        assert snapshot.tablet_strength_mg == Decimal("20")

    # Subsequent order changes do not rewrite past actual intake.
    edited = post(client, "/regimen/schedules/1/edit", {
        "cadence": "daily", "start_on": "2026-11-21", "active": "yes",
        "tablet_mode": "tablet", "tablet_strength_mg": "20",
        "prescribed_dose_mg": "5", "tablets_planned": "0.25",
        "meal": "",
    })
    assert "err=" not in edited.headers["location"]
    with Session() as db:
        assert db.get(RegimenSchedule, 1).amount == "0.25 tablets (5 mg)"
        assert db.get(RegimenTabletEntry731, 1).prescribed_dose_mg == Decimal("10")
        assert db.get(RegimenEntry, 1).amount == "0.5 tablets (10 mg)"

    # An actual history correction can record less than ordered while
    # retaining the original reference (no silent order rewrite).
    correction = post(client, "/regimen/entries/1/edit", {
        **intake_fields(tablet_count="0.25", tablet_edit_snapshot="yes"),
        "tablet_strength_mg": "20", "prescribed_dose_mg": "10",
    })
    assert "err=" not in correction.headers["location"]
    with Session() as db:
        assert db.get(RegimenEntry, 1).amount == "0.25 tablets (5 mg)"
        snapshot = db.get(RegimenTabletEntry731, 1)
        assert snapshot.tablets_taken == Decimal("0.25")
        assert snapshot.administered_dose_mg == Decimal("5")
        assert snapshot.prescribed_dose_mg == Decimal("10")
        assert db.scalar(select(ChangeAudit).where(
            ChangeAudit.entity_type == "regimen_tablet_entry",
            ChangeAudit.action == "edit",
        )) is not None


def test_731_manual_quick_log_skipped_and_conversion_to_manual(env):
    client, Session = env
    make_item(client)
    direct = post(client, "/regimen/entries", intake_fields(
        schedule_id="", tablet_strength_mg="20", prescribed_dose_mg="10"
    ))
    assert "err=" not in direct.headers["location"]
    with Session() as db:
        saved = db.get(RegimenTabletEntry731, 1)
        assert saved.tablets_taken == Decimal("0.5")
        assert saved.administered_dose_mg == Decimal("10")
        assert db.get(RegimenEntry, 1).amount == "0.5 tablets (10 mg)"

    manual = post(client, "/regimen/entries/1/edit", {
        "item_id": "1", "logged_at": "2026-11-21T09:30",
        "outcome": "taken", "amount": "1 capsule",
        "tablet_mode": "manual", "meal": "",
    })
    assert "err=" not in manual.headers["location"]
    with Session() as db:
        assert db.get(RegimenEntry, 1).amount == "1 capsule"
        assert db.get(RegimenTabletEntry731, 1) is None

    skipped = post(client, "/regimen/entries", intake_fields(
        schedule_id="", outcome="skipped",
        tablet_strength_mg="20", prescribed_dose_mg="10",
        logged_at="2026-11-22T09:30",
    ))
    assert "err=" not in skipped.headers["location"]
    with Session() as db:
        assert db.get(RegimenEntry, 2).amount == ""
        assert db.get(RegimenTabletEntry731, 2) is None

    removed = post(client, "/regimen/entries/1/delete")
    assert "err=" not in removed.headers["location"]
    with Session() as db:
        assert db.get(RegimenEntry, 1) is None
        assert db.get(RegimenTabletEntry731, 1) is None


@pytest.mark.parametrize("bad", [
    {"tablets_planned": "0.33"},
    {"tablets_planned": "-0.5"},
    {"tablet_strength_mg": "0"},
    {"tablet_strength_mg": "NaN"},
    {"tablet_strength_mg": "Infinity"},
    {"prescribed_dose_mg": "15"},
    {"prescribed_dose_mg": "10001"},
    {"tablet_strength_mg": "3.3333"},
    {"tablet_mode": "foreign"},
])
def test_731_bad_or_inconsistent_orders_fail_closed(env, bad):
    client, Session = env
    make_item(client)
    response = post(client, "/regimen/schedules", plan_fields(**bad))
    assert "err=" in response.headers["location"]
    with Session() as db:
        assert list(db.scalars(select(RegimenSchedule))) == []
        assert list(db.scalars(select(RegimenTabletSchedule731))) == []


@pytest.mark.parametrize("bad", ["0.1", "NaN", "20.25", "100", "-1"])
def test_731_bad_actual_tablet_count_does_not_create_intake(env, bad):
    client, Session = env
    make_item(client)
    post(client, "/regimen/schedules", plan_fields())
    response = post(client, "/regimen/entries", intake_fields(
        tablet_count=bad
    ))
    assert "err=" in response.headers["location"]
    with Session() as db:
        assert list(db.scalars(select(RegimenEntry))) == []
        assert list(db.scalars(select(RegimenTabletEntry731))) == []


def test_731_supplements_cannot_enter_tablet_mode(env):
    client, Session = env
    make_item(client, kind="supplement")
    result = post(client, "/regimen/schedules", plan_fields())
    assert "err=" in result.headers["location"]
    result = post(client, "/regimen/entries", intake_fields(
        schedule_id="", tablet_strength_mg="20", prescribed_dose_mg="10"
    ))
    assert "err=" in result.headers["location"]


def test_731_existing_non_tablet_regimen_remains_unchanged(env):
    client, Session = env
    make_item(client, kind="supplement")
    schedule = post(client, "/regimen/schedules", {
        "item_id": "1", "cadence": "daily", "start_on": "2026-11-21",
        "amount": "2 capsules", "meal": "",
    })
    assert "err=" not in schedule.headers["location"]
    entry = post(client, "/regimen/entries", {
        "item_id": "1", "schedule_id": "1",
        "logged_at": "2026-11-21T09:00", "outcome": "taken",
        "amount": "2 capsules", "meal": "",
    })
    assert "err=" not in entry.headers["location"]
    with Session() as db:
        assert db.get(RegimenSchedule, 1).amount == "2 capsules"
        assert db.get(RegimenEntry, 1).amount == "2 capsules"
        assert db.get(RegimenTabletSchedule731, 1) is None
        assert db.get(RegimenTabletEntry731, 1) is None


def test_731_calculation_and_safe_label_parsing():
    assert amount(Decimal("0.5"), Decimal("10")) == "0.5 tablets (10 mg)"
    assert schedule_values("20", "10", "0.5")["tablets_planned"] == Decimal("0.5")
    assert entry_values("20", "10", "0.25")["administered_dose_mg"] == Decimal("5")
    assert catalog_tablet_strength("20 mg") == "20"
    assert catalog_tablet_strength("20 mg per tablet") == "20"
    assert catalog_tablet_strength("200 mg/mL") == ""
    assert catalog_tablet_strength("10 mg/5 mL") == ""



def test_731_regimen_jinja_template_balanced_and_actual_get_renders(env):
    # The original 635 page must render even without tablet schedules.
    template = (Path(__file__).resolve().parents[1] /
                "app/templates/regimen635.html").read_text(encoding="utf-8")
    Environment().parse(template)
    client, Session = env
    make_item(client)
    page = client.get("/regimen?day=2026-11-21")
    assert page.status_code == 200
    assert "Example tablet" in page.text
    assert "Medication tablet quantity" in page.text
    assert 'tracker-regimen-tablets731.js?v=731' in page.text
    assert "data-reg731-item" in page.text
    assert "data-reg731-panel" in page.text
    post(client, "/regimen/schedules", plan_fields())
    page = client.get("/regimen?day=2026-11-21")
    assert page.status_code == 200
    assert 'data-reg731-due' in page.text
    assert "Ordered 10 mg from 20 mg/tablet" in page.text
    assert 'name="tablet_count"' in page.text
