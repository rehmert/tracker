"""Read-only Vitals ranges, summaries, history, and CSV contract tests."""
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import config, metrics
from app.db import Base, get_db
from app.main import app
from app.models import VitalReading


@pytest.fixture
def vitals_client(monkeypatch):
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
        now = datetime.now()
        old = now - timedelta(days=365 * 12)
        mid = now - timedelta(days=15)
        recent = now - timedelta(days=3)
        with Session(engine) as db:
            db.add_all([
                VitalReading(measured_at=old, weight_kg=100, context="Ancient reading"),
                VitalReading(measured_at=mid, weight_kg=90, context="Mid reading"),
                VitalReading(measured_at=recent, weight_kg=80, context="Recent reading"),
            ])
            db.commit()
        with TestClient(app) as client:
            yield client, engine
    finally:
        engine.dispose()


def test_vitals_all_is_unlimited_and_presets_are_real(vitals_client):
    client, engine = vitals_client
    seven = client.get("/vitals", params={"days": 7, "events": 0})
    assert seven.status_code == 200
    assert "Recent reading" in seven.text
    assert "Mid reading" not in seven.text
    assert "Ancient reading" not in seven.text
    assert seven.text.count('data-vitals-when=') == 1

    month = client.get("/vitals", params={"days": 30, "events": 0})
    assert "Mid reading" in month.text
    assert "Ancient reading" not in month.text

    six_months = client.get("/vitals", params={"days": 180, "events": 0})
    assert six_months.status_code == 200
    assert "Mid reading" in six_months.text

    all_history = client.get("/vitals", params={"days": 3650, "events": 0})
    assert all_history.status_code == 200
    assert "Ancient reading" in all_history.text
    assert all_history.text.count('data-vitals-when=') == 3
    assert 'data-vitals-weight-unit="' + config.WEIGHT_UNIT + '"' in all_history.text
    assert "View health timeline" in all_history.text
    assert "/exports/vitals.csv" in all_history.text
    with Session(engine) as db:
        assert len(list(db.scalars(select(VitalReading)))) == 3


def test_seven_day_view_keeps_honest_thirty_day_averages(vitals_client):
    client, _ = vitals_client
    page = client.get("/vitals", params={"days": 7, "events": 0})
    assert page.status_code == 200
    recent = metrics.weight_from_kg(80, config.WEIGHT_UNIT)
    mid = metrics.weight_from_kg(90, config.WEIGHT_UNIT)
    expected_7 = f"{recent:.1f}"
    expected_30 = f"{(recent + mid) / 2:.1f}"
    assert "7-day average" in page.text
    assert "30-day average" in page.text
    assert f"<dd>{expected_7}</dd>" in page.text
    assert f"<dd>{expected_30}</dd>" in page.text
    assert "Mid reading" not in page.text


def test_empty_vitals_page_keeps_existing_toolbar(vitals_client):
    client, _ = vitals_client
    page = client.get("/vitals", params={"days": 7, "events": 0})
    assert 'data-vitals-toolbar' in page.text
    assert 'data-vitals-search' in page.text
    assert 'data-vitals-export' in page.text
    assert 'data-vitals-table' in page.text


def test_vitals_jinja_and_js_contract():
    template = (Path(__file__).parents[1] / "app/templates/vitals.html").read_text()
    js = (Path(__file__).parents[1] / "app/static/js/tracker-vitals-tools.js").read_text()
    assert 'data-vitals-when="{{ r.measured_at.isoformat() }}"' in template
    assert 'data-vitals-weight-unit="{{ unit }}"' in template
    assert "row.dataset.vitalsWhen" in js
    assert "table.dataset.vitalsWeightUnit" in js
