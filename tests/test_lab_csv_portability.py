"""Read-only CSV export and blank layout reuse."""

import csv
import io
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import LabReport, LabResult


@pytest.fixture
def lab_client(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
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


def seed(engine):
    with Session(engine) as db:
        report = LabReport(
            drawn_on=date(2026, 11, 3),
            lab_name="Example Laboratory",
        )
        report.results = [
            LabResult(
                analyte="TSH",
                value=0.012345678901,
                unit="mIU/L",
                ref_low=0.45,
                ref_high=4.5,
                note="Confirmed",
            ),
            LabResult(
                analyte="=2+2",
                value=4.0,
                unit="ng/mL",
                ref_low=None,
                ref_high=None,
                note="@spreadsheet",
            ),
        ]
        db.add(report)
        db.commit()
        return report.id


def counts(engine):
    with Session(engine) as db:
        return (
            db.scalar(
                select(func.count()).select_from(LabReport)
            ),
            db.scalar(
                select(func.count()).select_from(LabResult)
            ),
        )


def read_csv(response):
    # Correct expectation: three actual BOM bytes,
    # not text containing backslash escape sequences.
    assert response.content.startswith(
        bytes.fromhex("efbbbf")
    )

    return list(csv.DictReader(
        io.StringIO(
            response.content.decode("utf-8-sig")
        )
    ))


def test_results_export_preserves_values(lab_client):
    client, engine = lab_client
    rid = seed(engine)
    before = counts(engine)

    response = client.get(
        f"/labs/{rid}/export.csv"
    )

    assert response.status_code == 200
    assert "attachment" in response.headers[
        "content-disposition"
    ]
    assert response.headers[
        "x-content-type-options"
    ] == "nosniff"

    rows = read_csv(response)

    assert len(rows) == 2
    assert rows[0]["drawn_on"] == "2026-11-03"
    assert rows[0]["lab_name"] == "Example Laboratory"
    assert rows[0]["analyte"] == "TSH"
    assert float(rows[0]["value"]) == 0.012345678901
    assert float(rows[0]["ref_low"]) == 0.45
    assert rows[0]["note"] == "Confirmed"

    assert rows[1]["analyte"].startswith("'=")
    assert rows[1]["note"].startswith("'@")
    assert counts(engine) == before


def test_template_excludes_previous_results(lab_client):
    client, engine = lab_client
    rid = seed(engine)
    before = counts(engine)

    response = client.get(
        f"/labs/{rid}/template.csv"
    )

    assert response.status_code == 200
    rows = read_csv(response)

    assert len(rows) == 2
    assert set(rows[0]) == {
        "analyte", "value", "unit",
        "ref_low", "ref_high", "note",
    }

    assert rows[0]["analyte"] == "TSH"
    assert rows[0]["unit"] == "mIU/L"

    for row in rows:
        for name in (
            "value", "ref_low", "ref_high", "note"
        ):
            assert row[name] == ""

    assert counts(engine) == before


def test_missing_report_returns_404(lab_client):
    client, _ = lab_client

    assert client.get(
        "/labs/999999/export.csv"
    ).status_code == 404

    assert client.get(
        "/labs/999999/template.csv"
    ).status_code == 404


def test_report_links(lab_client):
    client, engine = lab_client
    rid = seed(engine)

    response = client.get(f"/labs/{rid}")

    assert response.status_code == 200
    assert (
        f'href="/labs/{rid}/export.csv"'
        in response.text
    )
    assert (
        f'href="/labs/{rid}/template.csv"'
        in response.text
    )
