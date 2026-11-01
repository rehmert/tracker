"""Health Timeline navigation and filtering regressions.

All record creation uses an independent in-memory database.
"""
import csv
import io
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


def _csv_rows(response):
    assert response.status_code == 200
    assert response.content.startswith(b"\xef\xbb\xbf")
    return list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))


def test_csv_export_matches_displayed_doses(timeline_records):
    client, ids = timeline_records
    response = client.get(
        "/health-timeline/export.csv",
        params={"days": 90, "event_type": "Dose", "q": "TESTED"},
    )
    rows = _csv_rows(response)
    assert "attachment; filename=" in response.headers["content-disposition"]
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert len(rows) == 1
    assert rows[0]["Event type"] == "Dose"
    assert rows[0]["Title"] == "Recorded timeline compound: 1 mg"
    assert "Tested note" in rows[0]["Details"]
    assert rows[0]["Record"] == f'/doses/{ids["dose"]}/edit'
    assert "Unwanted what-if regimen" not in response.text


def test_csv_export_honors_all_history_and_active_status(timeline_records):
    client, _ = timeline_records
    recent = _csv_rows(client.get(
        "/health-timeline/export.csv", params={"days": 90, "event_type": "Vital"},
    ))
    assert len(recent) == 1

    all_rows = _csv_rows(client.get(
        "/health-timeline/export.csv", params={"days": 3650},
    ))
    assert len(all_rows) == 7
    assert sum(row["Event type"] == "Vital" for row in all_rows) == 2
    assert sum(row["Event type"] == "Protocol" for row in all_rows) == 2
    assert all("Unwanted what-if regimen" not in row["Title"] for row in all_rows)


def test_csv_export_empty_selection_still_has_headers(timeline_records):
    client, _ = timeline_records
    response = client.get(
        "/health-timeline/export.csv",
        params={"event_type": "Lab", "q": "not-real"},
    )
    assert response.status_code == 200
    assert _csv_rows(response) == []
    assert response.text.count("Date and time") == 1


@pytest.mark.parametrize("unsafe", [
    "=1+1", " +SUM(A1:A2)", "-1+2", "@SUM(1,1)", "\t=3*3",
    "\r+2+2", "\n@SUM(1,1)"
])
def test_csv_formula_protection(unsafe):
    from app.routers.health_timeline import _csv_safe
    result = _csv_safe(unsafe)
    assert result.startswith("'")
    assert result[1:] == unsafe


def test_csv_export_control_uses_current_form_filters(timeline_records):
    client, _ = timeline_records
    page = client.get("/health-timeline", params={"q": "CBC", "event_type": "Lab"})
    assert page.status_code == 200
    assert 'formaction="/health-timeline/export.csv"' in page.text
    assert 'formmethod="get"' in page.text
    assert 'value="CBC"' in page.text
    assert 'value="Lab" selected' in page.text
