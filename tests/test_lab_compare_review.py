"""Read-only Lab Report Comparison: coverage, unit handling and navigation."""
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
def compare_client(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    def override_db():
        with Session(engine) as db:
            yield db

    monkeypatch.setitem(app.dependency_overrides, get_db, override_db)
    try:
        with TestClient(app) as client:
            yield client, engine
    finally:
        engine.dispose()


def populate(engine):
    with Session(engine) as db:
        older = LabReport(drawn_on=date(2026, 7, 7), lab_name="First laboratory")
        older.results = [
            LabResult(analyte="TSH", value=0.2, unit="mIU/L"),
            LabResult(analyte="Total Testosterone", value=20.8, unit="nmol/L"),
            LabResult(analyte="Ferritin", value=250, unit="mg/L"),
            LabResult(analyte="PSA", value=0.54, unit="ng/mL"),
        ]
        newer = LabReport(drawn_on=date(2026, 11, 3), lab_name="Second laboratory")
        newer.results = [
            LabResult(analyte="TSH", value=0.2, unit="mIU/L"),
            LabResult(analyte="Total Testosterone", value=600, unit="ng/dL"),
            LabResult(analyte="Ferritin", value=200, unit="ng/mL"),
            LabResult(analyte="Albumin", value=4.1, unit="g/dL"),
        ]
        db.add_all([older, newer])
        db.commit()
        return newer.id, older.id


def test_compare_without_two_reports_keeps_navigation(compare_client):
    client, engine = compare_client
    response = client.get("/labs/compare")
    assert response.status_code == 200
    assert "At least two lab reports are needed" in response.text
    assert 'href="/labs/new"' in response.text
    assert "lab-compare-table" not in response.text
    with Session(engine) as db:
        db.add(LabReport(drawn_on=date(2026, 10, 1), lab_name="Only report"))
        db.commit()
    response = client.get("/labs/compare")
    assert response.status_code == 200
    assert "At least two lab reports are needed" in response.text


def test_compare_classifies_all_five_cases_and_preserves_db(compare_client):
    client, engine = compare_client
    newer_id, older_id = populate(engine)

    with Session(engine) as db:
        before = (
            db.scalar(select(func.count()).select_from(LabReport)),
            db.scalar(select(func.count()).select_from(LabResult)),
        )
    response = client.get("/labs/compare")
    assert response.status_code == 200
    html = response.text
    for marker in (
        'id="lab-compare-results"',
        'id="lab-compare-table"',
        'id="lab-compare-search"',
        'id="lab-compare-filter"',
        'id="lab-compare-sort"',
        'id="lab-compare-export"',
        'id="lab-compare-reset"',
        'id="lab-compare-count"',
        'data-report-a-date="2026-11-03"',
        'data-report-b-date="2026-07-07"',
        'data-state="same"',
        'data-state="different"',
        'data-state="incompatible"',
        'data-state="only-a"',
        'data-state="only-b"',
        'data-a-value="600.0"',
        'data-b-value="20.8"',
        'data-b-converted="',
        "Units not convertible",
        "Nonzero numeric difference",
        "Zero numeric difference",
        "Report B in A units",
        "Export filtered CSV",
    ):
        assert marker in html, marker

    assert html.count("data-lab-compare-row") == 5
    assert f'href="/labs/{newer_id}"' in html
    assert f'href="/labs/{older_id}"' in html
    assert (
        f'href="/labs/compare?first_id={older_id}&amp;second_id={newer_id}"'
        in html
    )
    with Session(engine) as db:
        after = (
            db.scalar(select(func.count()).select_from(LabReport)),
            db.scalar(select(func.count()).select_from(LabResult)),
        )
    assert before == after


def test_swap_and_duplicate_selection_are_explicit(compare_client):
    client, engine = compare_client
    newer_id, older_id = populate(engine)

    swapped = client.get(
        "/labs/compare", params={"first_id": older_id, "second_id": newer_id}
    )
    assert swapped.status_code == 200
    assert 'data-report-a-date="2026-07-07"' in swapped.text
    assert 'data-report-b-date="2026-11-03"' in swapped.text
    assert f'href="/labs/compare?first_id={newer_id}&amp;second_id={older_id}"' in swapped.text

    duplicate = client.get(
        "/labs/compare", params={"first_id": older_id, "second_id": older_id}
    )
    assert duplicate.status_code == 200
    assert "The same report is selected for A and B." in duplicate.text
    assert duplicate.text.count("data-state=") == 4
    assert 'data-state="same"' in duplicate.text


def test_comparison_front_end_is_display_only():
    template = (ROOT / "app/templates/lab_compare.html").read_text()
    script = (ROOT / "app/static/js/tracker-lab-compare-review.js").read_text()
    assert 'tracker-lab-compare-review.js?v=20261103' in template
    assert 'tracker-lab-compare-review.css?v=20261103' in template
    assert 'data-b-converted="{{ r.converted if r.comparable else ' in template
    assert 'data-delta="{{ r.delta if r.comparable else ' in template
    assert "visibleRows()" in script
    assert "exportFilteredCsv()" in script
    assert "'\\uFEFF'" in script
    assert "csvCell(value" in script
    assert "URL.createObjectURL" in script
    assert "fetch(" not in script
    assert "localStorage" not in script
    assert "sessionStorage" not in script
    assert ".submit(" not in script
