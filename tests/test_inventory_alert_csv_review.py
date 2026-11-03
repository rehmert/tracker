"""Inventory Alerts triage export: read-only HTML and JS regression contracts."""
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import Compound, Vial

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def alert_client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    def override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db] = override
    try:
        with TestClient(app) as client:
            yield client, engine
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_empty_alert_view_retains_read_only_workflow(alert_client):
    client, _ = alert_client
    page = client.get("/inventory-alerts", params={"days": 30, "horizon": 7})
    assert page.status_code == 200
    assert "0 alerts within the selected horizon" in page.text
    assert 'class="alert-table"' in page.text
    assert "No alerts for the selected horizon" in page.text
    assert "They do not acknowledge, dismiss, or change inventory records" in page.text
    assert "tracker-inventory-alert-triage.js?v=20261103-csv" in page.text
    assert "tracker-inventory-alert-triage.css?v=20261103-csv" in page.text


def test_alerts_render_current_server_values_without_writes(alert_client):
    client, engine = alert_client
    deadline = date.today() + timedelta(days=3)
    with Session(engine) as session:
        compound = Compound(name="Inventory CSV Check", category="peptide")
        session.add(compound)
        session.flush()
        session.add(Vial(compound_id=compound.id, label="Batch A",
                         content_value=10, content_unit="mg",
                         status="sealed", expires_on=deadline))
        session.commit()
        before_vials = session.scalar(select(func.count()).select_from(Vial))

    page = client.get("/inventory-alerts", params={"days": 30, "horizon": 7})
    assert page.status_code == 200
    assert "Inventory CSV Check" in page.text
    assert "Expiration in " in page.text
    assert deadline.isoformat() in page.text
    assert "alert-warning" in page.text

    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(Vial)) == before_vials


def test_alert_csv_reads_visible_rows_and_escapes_spreadsheet_values():
    script = (
        ROOT / "app/static/js/tracker-inventory-alert-triage.js"
    ).read_text()
    for marker in (
        "Export filtered CSV",
        "function csvCell(value)",
        "function exportFilteredCsv()",
        "records.filter(record => !record.row.hidden)",
        "tracker-inventory-alerts-filtered.csv",
        "tracker-triage-breakdown",
        "priorityCounts.set(",
        "exportButton.disabled = visible === 0",
        "URL.createObjectURL(blob)",
        "safe.replaceAll",
        r"'\uFEFF'",
        r"'\r\n'",
    ):
        assert marker in script, marker
    assert "fetch(" not in script
    assert ".submit(" not in script
    assert "XMLHttpRequest" not in script
