"""Release 514: finite manual lab measurements and reference intervals.

Isolated SQLite only. No installed Tracker database or live account is used.
"""

from datetime import date
import math

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import LabReport, LabResult
from app.routers.labs import _parse_rows, _parse_csv_data


@pytest.mark.parametrize(("measurement", "low", "high"), [
    ("nan", "", ""),
    ("NaN", "", ""),
    ("Infinity", "", ""),
    ("-inf", "", ""),
    ("1", "nan", "2"),
    ("1", "1", "Infinity"),
    ("1", "-inf", "2"),
    ("1", "nan", "nan"),
])
def test_514_manual_parser_rejects_nonfinite_numbers(measurement, low, high):
    parsed, echoed, error = _parse_rows(
        ["TSH"], [measurement], ["mIU/L"], [low], [high]
    )
    assert parsed == []
    assert error is not None and "finite" in error.lower()
    assert echoed[0]["value"] == measurement


@pytest.mark.parametrize(("measurement", "low", "high"), [
    ("0", "", ""),
    ("-1.2", "-2", "2"),
    ("1.25", "0.4", "4.5"),
    ("1e-8", "0", "1"),
])
def test_514_manual_parser_preserves_valid_finite_results(
    measurement, low, high
):
    parsed, _, error = _parse_rows(
        ["TSH"], [measurement], ["mIU/L"], [low], [high]
    )
    assert error is None
    assert len(parsed) == 1
    assert math.isfinite(parsed[0].value)
    assert parsed[0].value == float(measurement)


def test_514_manual_and_csv_entry_enforce_same_finite_policy():
    bad, _, error = _parse_rows(
        ["IGF-1"], ["nan"], ["ng/mL"], ["80"], ["250"]
    )
    assert not bad and error
    with pytest.raises(ValueError, match="finite"):
        _parse_csv_data(
            b"analyte,value,unit,ref_low,ref_high\n"
            b"IGF-1,nan,ng/mL,80,250\n"
        )


@pytest.fixture
def lab_client_514():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
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


def test_514_invalid_manual_report_cannot_write_nonfinite_rows(lab_client_514):
    client, engine = lab_client_514
    response = client.post(
        "/labs",
        data={
            "drawn_on": date(2026, 11, 8).isoformat(),
            "lab_name": "Isolated lab QA",
            "analyte": "IGF-1",
            "value": "NaN",
            "unit": "ng/mL",
            "ref_low": "80",
            "ref_high": "250",
        },
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert "finite" in response.text.lower()
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(LabReport)) == 0
        assert db.scalar(select(func.count()).select_from(LabResult)) == 0
