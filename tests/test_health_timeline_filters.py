"""Health Timeline navigation and filtering regressions.

All record creation uses an independent in-memory database.
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
def timeline_records():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)

    def override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override
    try:
        date_recent = date.today() - timedelta(days=4)
        date_old = date.today() - timedelta(days=365 * 12)
        with Session(engine) as db:
            active = Protocol(
                name="Active timeline regimen", is_active=True,
                start_date=date_recent, end_date=date_recent + timedelta(days=1),
            )
            what_if = Protocol(
                name="Unwanted what-if regimen", is_active=False,
                start_date=date_recent, end_date=date_recent + timedelta(days=1),
            )
            compound = Compound(name="Recorded timeline compound")
            vial = Vial(compound=compound, content_value=10, content_unit="mg")
            taken = datetime.combine(date_recent, datetime.min.time())
            dose = DoseLog(
                vial=vial, taken_at=taken, entered_value=1,
                entered_unit="mg", amount_base=1000, kind="dose",
                site="Left arm", notes="Tested note",
            )
            waste = DoseLog(
                vial=vial, taken_at=taken + timedelta(hours=1), entered_value=.5,
                entered_unit="mg", amount_base=500, kind="waste",
            )
            vital = VitalReading(
                measured_at=taken, weight_kg=89, context="morning",
                notes="After walking",
            )
            old_vital = VitalReading(
                measured_at=datetime.combine(date_old, datetime.min.time()),
                weight_kg=95,
            )
            report = LabReport(drawn_on=date_recent, lab_name="Lab timeline CBC")
            db.add_all([
                active, what_if, dose, waste, vital, old_vital, report,
            ])
            db.commit()
            ids = {
                "active": active.id, "dose": dose.id,
                "waste": waste.id, "vital": vital.id, "lab": report.id,
            }
        with TestClient(app) as client:
            yield client, ids
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_default_view_retains_all_records_but_only_active_protocols(timeline_records):
    client, ids = timeline_records
    r = client.get("/health-timeline")
    assert r.status_code == 200
    assert "Active timeline regimen · start date" in r.text
    assert "Active timeline regimen · end date" in r.text
    assert "Unwanted what-if regimen" not in r.text
    assert "Recorded timeline compound: 1 mg" in r.text
    assert "Recorded timeline compound: 0.5 mg" in r.text
    assert "Lab timeline CBC" in r.text
    assert "morning · After walking" in r.text
    assert "Showing 6 of 6 events" in r.text
    assert 'class="timeline-day-group"' in r.text
    assert f'href="/protocols/{ids["active"]}"' in r.text
    assert f'href="/doses/{ids["dose"]}/edit"' in r.text
    assert f'href="/doses/{ids["waste"]}/edit"' in r.text
    assert f'href="/vitals/{ids["vital"]}/edit"' in r.text
    assert f'href="/labs/{ids["lab"]}"' in r.text


@pytest.mark.parametrize(
    "kind, expected, excluded",
    [
        ("Dose", "Recorded timeline compound: 1 mg", "Active timeline regimen"),
        ("Waste", "Recorded timeline compound: 0.5 mg", "Lab timeline CBC"),
        ("Vital", "Weight", "Recorded timeline compound"),
        ("Lab", "Lab timeline CBC", "Active timeline regimen"),
        ("Protocol", "Active timeline regimen", "Lab timeline CBC"),
    ],
)
def test_filter_by_event_type(timeline_records, kind, expected, excluded):
    client, _ = timeline_records
    r = client.get("/health-timeline", params={"event_type": kind})
    assert r.status_code == 200
    assert expected in r.text
    assert excluded not in r.text
    assert "Unwanted what-if regimen" not in r.text
    assert "Showing " in r.text


def test_search_is_case_insensitive_and_filterable(timeline_records):
    client, _ = timeline_records
    r = client.get("/health-timeline", params={"q": "cBc", "event_type": "Lab"})
    assert r.status_code == 200
    assert "Lab timeline CBC" in r.text
    assert "Recorded timeline compound" not in r.text
    empty = client.get(
        "/health-timeline", params={"q": "no matching record", "event_type": "Lab"}
    )
    assert empty.status_code == 200
    assert "No entries match these filters" in empty.text
    assert "Unwanted what-if regimen" not in empty.text


def test_bad_filters_are_normalized(timeline_records):
    client, _ = timeline_records
    r = client.get(
        "/health-timeline", params={"days": -1, "event_type": "unknown", "q": "  "}
    )
    assert r.status_code == 200
    assert "Active timeline regimen" in r.text
    assert "Unwanted what-if regimen" not in r.text


def test_all_range_includes_more_than_ten_years(timeline_records):
    client, _ = timeline_records
    recent = client.get("/health-timeline?days=90&event_type=Vital")
    assert "Showing 1 of 6 events" in recent.text
    unlimited = client.get("/health-timeline?days=3650&event_type=Vital")
    assert unlimited.status_code == 200
    assert "Showing 2 of 7 events" in unlimited.text
