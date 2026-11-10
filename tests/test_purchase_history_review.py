"""Purchase history review is read-only, with explicit incomplete-order cues."""
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import Compound, Purchase, Vial


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def purchase_history_client(monkeypatch):
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


def test_empty_purchase_history_preserves_new_order_workflow(purchase_history_client):
    client, _ = purchase_history_client
    page = client.get("/purchases")
    assert page.status_code == 200
    assert 'id="purchase-history-table"' in page.text
    assert 'data-purchase-history' in page.text
    assert 'data-purchase-search' in page.text
    assert 'data-purchase-export' in page.text
    assert 'data-purchase-visible-count>0</strong>' in page.text
    assert 'data-purchase-needs-count>0</strong>' in page.text
    assert 'colspan="7" class="empty">No purchases yet.' in page.text
    assert '<form method="post" action="/purchases"' in page.text
    assert 'name="submission_token"' in page.text


def test_purchase_history_shows_missing_items_and_allocated_totals(purchase_history_client):
    client, engine = purchase_history_client
    with Session(engine) as db:
        missing = Purchase(
            vendor="Vendor One", order_ref="INV-101",
            purchased_on=date(2026, 11, 3), shipping_cents=999
        )
        ready = Purchase(
            vendor="Vendor Two", order_ref="INV-102",
            purchased_on=date(2026, 10, 30)
        )
        compound = Compound(name="Inventory History Sample", category="peptide")
        db.add_all([missing, ready, compound])
        db.flush()
        vial = Vial(
            purchase_id=ready.id, compound_id=compound.id,
            status="sealed", content_value=10, content_unit="mg",
            unit_price_cents=2200
        )
        db.add(vial)
        db.commit()
        missing_id, ready_id = missing.id, ready.id
        count_before = db.scalar(select(func.count()).select_from(Purchase))
        vials_before = db.scalar(select(func.count()).select_from(Vial))

    page = client.get("/purchases")
    assert page.status_code == 200
    markup = page.text
    for marker in (
        'data-purchase-search',
        'data-purchase-vendor',
        'data-purchase-status',
        'data-purchase-from',
        'data-purchase-through',
        'data-purchase-reset',
        'data-purchase-export',
        'data-purchase-needs-count>1</strong>',
        'data-purchase-visible-count>2</strong>',
        'data-purchase-visible-total',
        'data-purchase-date="2026-11-03"',
        'data-purchase-vendor="Vendor One"',
        'data-purchase-order="INV-101"',
        'data-purchase-status="needs-items"',
        'data-purchase-status="has-items"',
        'data-purchase-total-cents="0"',
        'data-purchase-total-cents="2200.0"',
        "Needs items · Add inventory",
        "Review items",
        "Filters, sorting and CSV exports do not change purchases or inventory.",
        'tracker-purchase-history-review.js?v=20261103',
        'tracker-purchase-history-review.css?v=20261103'
    ):
        assert marker in markup, marker
    assert markup.count('data-purchase-row') == 2
    assert f'href="/purchases/{missing_id}"' in markup
    assert f'href="/purchases/{ready_id}"' in markup
    assert 'data-enhanced-table' not in (ROOT / "app/templates/purchases.html").read_text()

    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Purchase)) == count_before
        assert db.scalar(select(func.count()).select_from(Vial)) == vials_before


def test_purchase_history_browser_contract_preserves_sort_and_safe_export():
    script = (
        ROOT / "app/static/js/tracker-purchase-history-review.js"
    ).read_text()
    for marker in (
        "function compare(a, b)",
        "function updateSortState()",
        "sortState.direction",
        "th.setAttribute('aria-sort'",
        "function csvCell(value, numeric = false)",
        "function exportCsv()",
        "visibleRows()",
        "data-purchase-row",
        "tracker-purchase-history-filtered.csv",
        "URL.createObjectURL(blob)",
        "exportButton.disabled = shown === 0",
        "from.value > through.value",
        "sumCents += cents(row)",
        r"'\uFEFF'",
        r"'\r\n'",
    ):
        assert marker in script, marker
    assert "fetch(" not in script
    assert "localStorage" not in script
    assert "sessionStorage" not in script
    assert ".submit(" not in script
