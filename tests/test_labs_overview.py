"""Lab overview search/range-status/sort is read-only and uses latest report ranges."""
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import LabReport, LabResult


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def lab_overview_client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    def override_db():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            yield client, engine
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_empty_overview_keeps_reports_search_available(lab_overview_client):
    client, _ = lab_overview_client
    response = client.get("/labs")
    assert response.status_code == 200
    assert 'id="labs-reports-table"' in response.text
    assert 'id="labs-report-search"' in response.text
    assert 'id="labs-reports-clear"' in response.text
    assert 'id="labs-reports-count"' in response.text
    assert "No lab reports yet." in response.text
    assert 'id="labs-trend-grid"' not in response.text


def test_latest_result_range_statuses_and_report_links(lab_overview_client):
    client, engine = lab_overview_client
    with Session(engine) as db:
        earlier = LabReport(drawn_on=date(2026, 7, 7), lab_name="Earlier Diagnostics")
        earlier.results = [
            LabResult(analyte="TSH", value=2.0, unit="mIU/L",
                      ref_low=0.4, ref_high=4.5),
        ]
        latest = LabReport(drawn_on=date(2026, 11, 1), lab_name="Current Diagnostics")
        latest.results = [
            LabResult(analyte="TSH", value=0.1, unit="mIU/L",
                      ref_low=0.4, ref_high=4.5),
            LabResult(analyte="Ferritin", value=520, unit="ng/mL",
                      ref_low=20, ref_high=300),
            LabResult(analyte="Glucose", value=90, unit="mg/dL",
                      ref_low=70, ref_high=99),
            LabResult(analyte="IGF-1", value=188, unit="ng/mL"),
        ]
        db.add_all([earlier, latest])
        db.commit()
        expected_report_count = db.scalar(select(func.count()).select_from(LabReport))
        expected_result_count = db.scalar(select(func.count()).select_from(LabResult))

    response = client.get("/labs")
    assert response.status_code == 200
    markup = response.text

    for marker in (
        'id="labs-trend-controls"',
        'id="labs-trend-grid"',
        'id="labs-analyte-search"',
        'id="labs-range-filter"',
        'id="labs-trend-sort"',
        'id="labs-trend-clear"',
        'id="labs-trend-count"',
        'id="labs-report-search"',
        'id="labs-reports-table"',
        'tracker-labs-overview.js?v=20261103',
        'tracker-labs-overview.css?v=20261103',
        'data-lab-status="below"',
        'data-lab-status="above"',
        'data-lab-status="within"',
        'data-lab-status="unknown"',
        'data-lab-name="TSH"',
        'data-lab-results="2"',
        'data-lab-date="2026-11-01"',
        'data-lab-report-date="2026-07-07"',
        'data-lab-report-name="Earlier Diagnostics"',
        "Outside printed range",
        "No printed range",
    ):
        assert marker in markup, marker

    assert markup.count("data-labs-trend-card") == 4
    assert markup.count("data-labs-report-row") == 2
    assert 'href="/labs/' in markup

    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(LabReport)) == expected_report_count
        assert db.scalar(select(func.count()).select_from(LabResult)) == expected_result_count


def test_overview_filtering_never_submits_labs(lab_overview_client):
    source = (ROOT / "app/static/js/tracker-labs-overview.js").read_text()
    assert "card.hidden = !show" in source
    assert "row.hidden = !show" in source
    assert "grid.appendChild(card)" in source
    assert "filter === 'outside'" in source
    assert "filter === 'unknown'" not in source  # compared against data status generically
    assert "window.fetch" not in source
    assert "fetch(" not in source
    assert ".submit(" not in source
    assert "localStorage" not in source
