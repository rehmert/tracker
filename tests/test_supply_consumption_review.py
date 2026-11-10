"""Supply consumption review: HTTP rendering, historical data, and no writes."""
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import Purchase, Supply, SupplyUsage


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def consumption_client(monkeypatch):
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


def seed_consumption(engine):
    recorded_at = datetime.now() - timedelta(days=1)
    with Session(engine) as db:
        purchase = Purchase(vendor="Usage tests", purchased_on=date(2026, 11, 3))
        db.add(purchase)
        db.flush()
        rows = [
            Supply(purchase_id=purchase.id, name="Needles", kind="needle",
                   purchased_qty=100, remaining_qty=8),
            Supply(purchase_id=purchase.id, name="Syringes", kind="syringe",
                   purchased_qty=20, remaining_qty=0),
            Supply(purchase_id=purchase.id, name="BAC Water", kind="bac_water",
                   purchased_qty=30, remaining_qty=30),
            Supply(purchase_id=purchase.id, name="Alcohol pads", kind="other",
                   purchased_qty=100, remaining_qty=100),
        ]
        db.add_all(rows)
        db.flush()
        db.add_all([
            SupplyUsage(supply_id=rows[0].id, amount=12,
                        created_at=recorded_at),
            SupplyUsage(supply_id=rows[1].id, amount=5,
                        created_at=recorded_at),
        ])
        db.commit()


def test_empty_supply_consumption_includes_controls_and_empty_state(consumption_client):
    client, _ = consumption_client
    response = client.get("/consumption")
    assert response.status_code == 200
    html = response.text
    for marker in (
        'id="supply-consumption-review"',
        'id="supply-consumption-table"',
        'id="supply-consumption-search"',
        'id="supply-consumption-filter"',
        'id="supply-consumption-sort"',
        'id="supply-consumption-export"',
        'id="supply-consumption-total">0</strong>',
        'colspan="6" class="empty"',
        'tracker-supply-consumption-review.js?v=20261103',
        'tracker-supply-consumption-review.css?v=20261103',
        'value="90" selected',
        "No supplies recorded.",
    ):
        assert marker in html, marker
    assert html.count("data-supply-consumption-row") == 0


def test_supply_coverage_and_summary_reflect_server_calculations_without_writes(consumption_client):
    client, engine = consumption_client
    seed_consumption(engine)
    with Session(engine) as db:
        before = (
            db.scalar(select(func.count()).select_from(Supply)),
            db.scalar(select(func.count()).select_from(SupplyUsage)),
            db.scalar(select(func.count()).select_from(Purchase)),
        )

    response = client.get("/consumption", params={"days": 30})
    assert response.status_code == 200
    html = response.text
    for marker in (
        'data-period-days="30"',
        'value="30" selected',
        'id="supply-consumption-total">4</strong>',
        'id="supply-consumption-used">2</strong>',
        'id="supply-consumption-zero">1</strong>',
        'id="supply-consumption-short">2</strong>',
        'data-supply-name="Needles"',
        'data-supply-kind="needle"',
        'data-supply-used="12.0"',
        'data-supply-remaining="8.0"',
        'data-supply-rate="0.4"',
        'data-supply-coverage="20.0"',
        'data-supply-name="Syringes"',
        'data-supply-remaining="0.0"',
        'data-supply-name="BAC Water"',
        'data-supply-coverage=""',
        'No usage in selected period',
        "Filtering, sorting, and exporting never change inventory.",
    ):
        assert marker in html, marker
    assert html.count("data-supply-consumption-row") == 4

    with Session(engine) as db:
        after = (
            db.scalar(select(func.count()).select_from(Supply)),
            db.scalar(select(func.count()).select_from(SupplyUsage)),
            db.scalar(select(func.count()).select_from(Purchase)),
        )
    assert before == after


def test_period_filter_is_preserved(consumption_client):
    client, engine = consumption_client
    seed_consumption(engine)
    response = client.get("/consumption", params={"days": 180})
    assert response.status_code == 200
    assert 'value="180" selected' in response.text
    assert 'data-period-days="180"' in response.text
    assert 'id="supply-consumption-total">4</strong>' in response.text


def test_supply_consumption_frontend_has_no_write_requests():
    script = (ROOT / "app/static/js/tracker-supply-consumption-review.js").read_text()
    for marker in (
        "function isMatch(record, query, state)",
        "function visible()",
        "function csvCell(value, numeric = false)",
        "function exportCsv()",
        "function update()",
        "table.dataset.consumptionReady = '1'",
        "URL.createObjectURL(blob)",
        "tracker-supply-consumption-filtered.csv",
        "exportButton.disabled = shown === 0",
        "record.coverage !== null && record.coverage <= 30",
        r"'\uFEFF'",
        r"'\r\n'",
    ):
        assert marker in script, marker
    assert "fetch(" not in script
    assert ".submit(" not in script
    assert "localStorage" not in script
    assert "sessionStorage" not in script
