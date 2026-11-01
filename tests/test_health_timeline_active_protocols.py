"""Health Timeline shows active protocol dates, never inactive what-if plans.

All tests use a standalone in-memory SQLite database. The running Tracker
database, files, and production service are never accessed by these tests.
"""
from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import Compound, DoseLog, LabReport, Protocol, Vial, VitalReading


@pytest.fixture
def timeline_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    def isolated_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = isolated_db
    try:
        with TestClient(app) as client:
            yield client, engine
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


@pytest.mark.parametrize("days", [30, 90, 365, 3650])
def test_timeline_only_includes_active_protocols_and_retains_records(
    timeline_client, days
):
    client, engine = timeline_client
    start = date.today() - timedelta(days=8)
    end = date.today() - timedelta(days=2)
    measured = datetime.combine(date.today() - timedelta(days=1), datetime.min.time())

    with Session(engine) as db:
        active = Protocol(
            name="Timeline ACTIVE plan", is_active=True,
            start_date=start, end_date=end,
        )
        draft = Protocol(
            name="Timeline DRAFT what-if", is_active=False,
            start_date=start, end_date=end,
        )
        no_dates = Protocol(name="Timeline ACTIVE without dates", is_active=True)
        compound = Compound(name="Timeline recorded compound")
        vial = Vial(compound=compound, content_value=10, content_unit="mg")
        dose = DoseLog(
            vial=vial, taken_at=measured,
            entered_value=1, entered_unit="mg", amount_base=1000,
            kind="dose",
        )
        vital = VitalReading(measured_at=measured, weight_kg=90)
        lab = LabReport(drawn_on=measured.date(), lab_name="Timeline recorded lab")
        db.add_all([active, draft, no_dates, dose, vital, lab])
        db.commit()
        active_id, draft_id = active.id, draft.id

    response = client.get(f"/health-timeline?days={days}")
    assert response.status_code == 200
    assert response.text.count("Timeline ACTIVE plan · start date") == 1
    assert response.text.count("Timeline ACTIVE plan · end date") == 1
    assert "Timeline DRAFT what-if" not in response.text
    assert "Timeline ACTIVE without dates" not in response.text
    assert "Timeline recorded compound: 1 mg" in response.text
    assert "Timeline recorded lab" in response.text
    assert "Weight" in response.text
    assert "What-if protocols are excluded" in response.text

    # Status changes should take effect immediately; dates and recorded
    # administrations remain unchanged.
    with Session(engine) as db:
        db.get(Protocol, active_id).is_active = False
        db.get(Protocol, draft_id).is_active = True
        db.commit()
    updated = client.get(f"/health-timeline?days={days}")
    assert updated.status_code == 200
    assert "Timeline ACTIVE plan" not in updated.text
    assert "Timeline DRAFT what-if · start date" in updated.text
    assert "Timeline DRAFT what-if · end date" in updated.text
    assert "Timeline recorded compound: 1 mg" in updated.text
    assert "Timeline recorded lab" in updated.text
